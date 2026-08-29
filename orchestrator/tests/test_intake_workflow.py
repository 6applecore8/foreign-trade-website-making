import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_intake_workflow


class IntakeWorkflowLaunchTests(unittest.TestCase):
    def test_provider_preflight_failure_happens_before_archive_or_config_promotion(self):
        project_root = Path(__file__).resolve().parents[2]
        manifest = {
            "run_id": "run-test-preflight",
            "request_id": "req-test",
        }
        with patch.object(
            run_intake_workflow,
            "load_launch_manifest",
            return_value=(manifest, project_root / "request.json", project_root / "candidate.json"),
        ), patch.object(run_intake_workflow, "validate_request"), patch.object(
            run_intake_workflow, "build_executor", side_effect=RuntimeError("provider unavailable")
        ), patch.object(run_intake_workflow, "archive_run") as archive, patch.object(
            run_intake_workflow, "promote_config"
        ) as promote:
            with self.assertRaisesRegex(RuntimeError, "provider unavailable"):
                run_intake_workflow.execute(project_root, project_root / "manifest.json")
        archive.assert_not_called()
        promote.assert_not_called()

    def test_manifest_path_outside_runtime_store_is_rejected(self):
        project_root = Path(__file__).resolve().parents[2]
        with self.assertRaises((ValueError, FileNotFoundError)):
            run_intake_workflow.load_launch_manifest(project_root, project_root / "workflow.json")


if __name__ == "__main__":
    unittest.main()
