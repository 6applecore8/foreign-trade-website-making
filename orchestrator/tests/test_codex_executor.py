import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from orchestrator.adapters.codex_executor import CodexExecutor
from orchestrator.executor import ExecutionRequest


class CodexExecutorTests(unittest.TestCase):
    def test_usage_limit_error_is_concise_and_does_not_echo_prompt(self):
        import subprocess

        result = subprocess.CompletedProcess(
            ["codex"],
            1,
            stdout="trusted role contract secret\n" * 500,
            stderr="ERROR: You've hit your usage limit. try again at 5:29 AM.\n",
        )
        detail = CodexExecutor._failure_detail(result)
        self.assertEqual("Codex usage limit reached; retry after 5:29 AM", detail)
        self.assertNotIn("trusted role contract", detail)

    def test_fake_cli_receipt_and_declared_output_are_accepted(self):
        project_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prompt = root / "prompt.md"
            source = root / "input.json"
            output = root / "artifact.json"
            fake = root / "fake_codex.py"
            prompt.write_text("write the artifact", encoding="utf-8")
            source.write_text("{}", encoding="utf-8")
            fake.write_text(
                """import json, pathlib, sys
args=sys.argv[1:]
if args == ['--version']:
 print('codex-cli test'); raise SystemExit(0)
if args == ['login','status']:
 print('Logged in using test'); raise SystemExit(0)
schema=pathlib.Path(args[args.index('--output-schema')+1])
receipt=pathlib.Path(args[args.index('--output-last-message')+1])
workspace=pathlib.Path(args[args.index('--cd')+1])
prompt=sys.stdin.read()
assert 'UNTRUSTED DATA' in prompt
(workspace/'artifact.json').write_text('{}',encoding='utf-8')
node=json.loads(schema.read_text(encoding='utf-8'))['properties']['node_id']['const']
receipt.write_text(json.dumps({'node_id':node,'status':'success','artifacts':['artifact.json'],'detail':'ok'}),encoding='utf-8')
""",
                encoding="utf-8",
            )
            executor = CodexExecutor(project_root, command=[sys.executable, str(fake)])
            executor.preflight()
            request = ExecutionRequest(
                "requirements", "1", root, prompt, (source,), (source,), (output,), None, (source,)
            )
            receipt = executor.run_agent(request)
            self.assertEqual("success", receipt.status, receipt.detail)
            self.assertTrue(output.is_file())

    def test_preflight_rejects_unsigned_cli(self):
        project_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "fake_codex.py"
            fake.write_text(
                "import sys\nprint('codex-cli test' if '--version' in sys.argv else 'Not logged in')\n",
                encoding="utf-8",
            )
            executor = CodexExecutor(project_root, command=[sys.executable, str(fake)])
            with self.assertRaisesRegex(RuntimeError, "not signed in"):
                executor.preflight()

    @unittest.skipUnless(os.environ.get("SITE_RUN_REAL_CODEX_TEST") == "1", "real Codex call is opt-in")
    def test_real_codex_cli_writes_only_the_declared_artifact(self):
        project_root = Path(__file__).resolve().parents[2]
        executor = CodexExecutor(project_root, timeout=180)
        executor.preflight()
        test_root = project_root / "runs" / ".test-sandboxes"
        test_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=test_root) as tmp:
            root = Path(tmp)
            prompt = root / "prompt.md"
            source = root / "input.json"
            output = root / "artifact.json"
            prompt.write_text(
                "Read input.json and write artifact.json as valid JSON with exactly the same object.",
                encoding="utf-8",
            )
            source.write_text('{"smoke":"ok"}\n', encoding="utf-8")
            output.touch()
            receipt = executor.run_agent(ExecutionRequest(
                "smoke", "1", root, prompt, (source,), (source,), (output,), None, (source,)
            ))
            self.assertEqual("success", receipt.status, receipt.detail)
            self.assertEqual({"smoke": "ok"}, json.loads(output.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
