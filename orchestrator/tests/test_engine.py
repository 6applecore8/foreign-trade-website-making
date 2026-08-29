import json
import tempfile
import unittest
from pathlib import Path

from orchestrator.acl import PermissionViolation, reject_unauthorized_changes, resolve_inside
from orchestrator.executor import AgentExecutor, ArtifactReceipt
from orchestrator.graph import GraphError, WorkflowGraph
from orchestrator.validators import DeterministicValidator


class FakeExecutor(AgentExecutor):
    def run_agent(self, request):
        for path in request.allowed_write_paths:
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text('{}', encoding='utf-8')
        return ArtifactReceipt(request.node_id, 'success', [str(p) for p in request.allowed_write_paths])


class CounterexampleTests(unittest.TestCase):
    SITE_FIXTURE_FILES = (
        'config/site-config.json',
        'artifacts/01-requirements/requirements.json',
        'artifacts/02-metadata/metadata.json',
        'artifacts/03-content/home-content.json',
        'artifacts/04-implementation/site/index.html',
        'artifacts/04-implementation/site/shoes.html',
        'artifacts/04-implementation/site/apparel.html',
        'artifacts/04-implementation/site/looks.html',
        'artifacts/04-implementation/site/styles.css',
        'artifacts/04-implementation/site/site-spec.json',
        'artifacts/04-implementation/site/hero-campaign.png',
        'artifacts/04-implementation/site/product-footwear.png',
        'artifacts/04-implementation/site/product-apparel.png',
        'artifacts/04-implementation/site/catalog-shoes.png',
        'artifacts/04-implementation/site/catalog-apparel.png',
        'artifacts/04-implementation/site/catalog-looks.png',
    )

    def copy_site_fixture(self, root, copy):
        for rel in self.SITE_FIXTURE_FILES:
            target = copy / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((root / rel).read_bytes())

    def test_implementation_cannot_finish_without_browser_collector(self):
        from orchestrator.runner import WorkflowRunner
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'prompts').mkdir(); (root / 'inputs').mkdir()
            (root / 'prompts/p.md').write_text('prompt', encoding='utf-8'); (root / 'inputs/a.json').write_text('{}', encoding='utf-8')
            (root / 'workflow.json').write_text(json.dumps({'version':'1','nodes':[{'id':'implementation','type':'subagent','prompt':'prompts/p.md','reads':['inputs/a.json'],'writes':['outputs/a.json']},{'id':'validation','type':'subagent','prompt':'prompts/p.md','reads':['outputs/a.json'],'writes':['outputs/validation.json']}],'edges':[['implementation','validation']]}),encoding='utf-8')
            result = WorkflowRunner(root, FakeExecutor()).run(run_id='no-browser')
            self.assertEqual('failed', result['status'])
            self.assertIn('browser evidence collector is required', result['error']['detail'])

    def test_executor_request_is_sandboxed(self):
        from orchestrator.runner import WorkflowRunner
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'prompts').mkdir(); (root / 'inputs').mkdir()
            (root / 'prompts/p.md').write_text('prompt', encoding='utf-8'); (root / 'inputs/a.json').write_text('{}', encoding='utf-8')
            (root / 'workflow.json').write_text(json.dumps({'version': '1', 'nodes': [{'id': 'a', 'type': 'subagent', 'prompt': 'prompts/p.md', 'reads': ['inputs/a.json'], 'writes': ['outputs/a.json']}], 'edges': []}), encoding='utf-8')
            class Inspecting(FakeExecutor):
                def run_agent(self, request):
                    self.request = request
                    self.asserted = request.execution_root != root and all(str(p).startswith(str(request.execution_root)) for p in request.allowed_read_paths + request.allowed_write_paths)
                    return super().run_agent(request)
            executor = Inspecting(); result = WorkflowRunner(root, executor).run(run_id='sandbox-test')
            self.assertEqual(result['status'], 'success'); self.assertTrue(executor.asserted)

    def test_failed_executor_does_not_promote_staged_output(self):
        from orchestrator.runner import WorkflowRunner
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'prompts').mkdir(); (root / 'inputs').mkdir(); (root / 'outputs').mkdir()
            (root / 'prompts/p.md').write_text('prompt', encoding='utf-8'); (root / 'inputs/a.json').write_text('{}', encoding='utf-8')
            output = root / 'outputs/a.json'; output.write_text('{"version":"trusted"}', encoding='utf-8')
            (root / 'workflow.json').write_text(json.dumps({'version': '1', 'nodes': [{'id': 'a', 'type': 'subagent', 'prompt': 'prompts/p.md', 'reads': ['inputs/a.json'], 'writes': ['outputs/a.json']}], 'edges': []}), encoding='utf-8')

            class FailingExecutor(AgentExecutor):
                def run_agent(self, request):
                    request.allowed_write_paths[0].write_text('{"version":"untrusted"}', encoding='utf-8')
                    return ArtifactReceipt(request.node_id, 'failed', [], 'declined')

            result = WorkflowRunner(root, FailingExecutor()).run(run_id='failed-promotion')
            self.assertEqual('failed', result['status'])
            self.assertEqual({'version': 'trusted'}, json.loads(output.read_text(encoding='utf-8')))

    def test_failed_validation_report_is_not_promoted(self):
        from orchestrator.runner import WorkflowRunner
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'prompts').mkdir(); (root / 'outputs').mkdir()
            (root / 'prompts/p.md').write_text('prompt', encoding='utf-8')
            report = root / 'outputs/validation.json'; report.write_text('{"status":"passed"}', encoding='utf-8')
            (root / 'workflow.json').write_text(json.dumps({
                'version': '1',
                'nodes': [{'id': 'validation', 'type': 'subagent', 'prompt': 'prompts/p.md', 'reads': [], 'writes': ['outputs/validation.json']}],
                'edges': [],
            }), encoding='utf-8')

            class FailedReviewExecutor(AgentExecutor):
                def run_agent(self, request):
                    request.allowed_write_paths[0].write_text('{"status":"failed"}', encoding='utf-8')
                    return ArtifactReceipt(request.node_id, 'success', [str(request.allowed_write_paths[0])])

            class PassingBrowserCollector:
                def collect(self, site_root, evidence_path, screenshot_path):
                    raise AssertionError('pre-validation fixture must fail before browser collection')

            # Exercise the staged-report contract directly through a minimal
            # validation run that bypasses only the unrelated browser gate.
            runner = WorkflowRunner(root, FailedReviewExecutor())
            runner._run_pre_validation_gate = lambda *args: None
            result = runner.run(run_id='failed-review')
            self.assertEqual('failed', result['status'])
            self.assertIn('validation report did not pass', result['error']['detail'])
            self.assertEqual({'status': 'passed'}, json.loads(report.read_text(encoding='utf-8')))

    def test_start_from_reuses_hashed_upstream_artifacts(self):
        from orchestrator.runner import WorkflowRunner
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'prompts').mkdir(); (root / 'outputs').mkdir()
            (root / 'prompts/p.md').write_text('prompt', encoding='utf-8')
            upstream = root / 'outputs/a.json'; upstream.write_text('{"status":"success"}', encoding='utf-8')
            workflow = {
                'version': '1',
                'nodes': [
                    {'id': 'a', 'type': 'subagent', 'prompt': 'prompts/p.md', 'reads': [], 'writes': ['outputs/a.json']},
                    {'id': 'b', 'type': 'subagent', 'prompt': 'prompts/p.md', 'reads': ['outputs/a.json'], 'writes': ['outputs/b.json']},
                ],
                'edges': [['a', 'b']],
            }
            (root / 'workflow.json').write_text(json.dumps(workflow), encoding='utf-8')

            class TrackingExecutor(FakeExecutor):
                calls = []
                def run_agent(self, request):
                    self.calls.append(request.node_id)
                    return super().run_agent(request)

            executor = TrackingExecutor()
            result = WorkflowRunner(root, executor).run(run_id='recovery', start_from='b')
            self.assertEqual('success', result['status'])
            self.assertEqual(['b'], executor.calls)
            self.assertIn('outputs/a.json', result['nodes']['reused-upstream-artifacts']['hashes'])

    def test_cycle_is_rejected(self):
        workflow = {'nodes': [{'id': 'a'}, {'id': 'b'}], 'edges': [['a', 'b'], ['b', 'a']]}
        with self.assertRaises(GraphError): WorkflowGraph(workflow)

    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PermissionViolation): resolve_inside(Path(tmp), '../secret.txt')

    def test_unauthorized_write_is_rejected(self):
        with self.assertRaises(PermissionViolation): reject_unauthorized_changes({'safe': 'a'}, {'safe': 'a', 'stolen': 'b'}, {'allowed'})

    def test_missing_requirement_is_not_allowed_to_pass(self):
        root = Path(__file__).parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            self.copy_site_fixture(root, copy)
            html = copy / 'artifacts/04-implementation/site/index.html'
            content = json.loads((copy / 'artifacts/03-content/home-content.json').read_text(encoding='utf-8'))
            headline = content['hero']['headline']
            source = html.read_text(encoding='utf-8')
            # Headline may be deliberately split into controlled inline spans.
            for part in [value for value in headline.replace('，', '，|').split('|') if value]:
                source = source.replace(part, '')
            html.write_text(source, encoding='utf-8')
            result = DeterministicValidator().validate(copy)
            self.assertEqual(result['status'], 'failed')
            self.assertTrue(any(check['name'] == 'requirements/content 覆盖率' and check['status'] == 'failed' for check in result['checks']))

    def test_reordered_faq_is_not_allowed_to_pass(self):
        root = Path(__file__).parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            self.copy_site_fixture(root, copy)
            html = copy / 'artifacts/04-implementation/site/index.html'
            source = html.read_text(encoding='utf-8')
            faq = json.loads((copy / 'config/site-config.json').read_text(encoding='utf-8'))['faq']['items']
            first, second = faq[0]['question'], faq[1]['question']
            source = source.replace(first, '__FAQ_SWAP__').replace(second, first).replace('__FAQ_SWAP__', second)
            html.write_text(source, encoding='utf-8')
            result = DeterministicValidator().validate(copy)
            self.assertEqual(result['status'], 'failed')
            self.assertTrue(any(check['name'] == 'FAQ 保真' and check['status'] == 'failed' for check in result['checks']))

    def test_category_with_four_products_is_not_allowed_to_pass(self):
        root = Path(__file__).parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            self.copy_site_fixture(root, copy)
            html = copy / 'artifacts/04-implementation/site/shoes.html'
            source = html.read_text(encoding='utf-8')
            marker = '<article class="product-card">' if '<article class="product-card">' in source else '<article class="catalog-card">'
            start = source.index(marker)
            end = source.index('</article>', start) + len('</article>')
            html.write_text(source[:start] + source[end:], encoding='utf-8')
            result = DeterministicValidator().validate(copy)
            self.assertEqual(result['status'], 'failed')
            self.assertTrue(any(check['name'] == '分类页面与商品数据' and check['status'] == 'failed' for check in result['checks']))


if __name__ == '__main__': unittest.main()
