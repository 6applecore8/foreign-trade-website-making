from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adapters import HermesExecutor
from .runner import WorkflowRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the repository Agent workflow")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--workflow", default="workflow.json")
    parser.add_argument("--run-id")
    parser.add_argument("--timeout", type=float)
    parser.add_argument("hermes_command", nargs="+", help="Hermes command; manifest path is appended")
    args = parser.parse_args()
    state = WorkflowRunner(args.root, HermesExecutor(args.hermes_command, timeout=args.timeout)).run(args.workflow, args.run_id)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0 if state["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
