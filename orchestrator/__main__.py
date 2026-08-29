from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adapters.codex_executor import CodexExecutor
from .adapters.hermes_executor import HermesExecutor
from .browser import PlaywrightBrowserEvidenceCollector
from .runner import WorkflowRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the repository Agent workflow")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--workflow", default="workflow.json")
    parser.add_argument("--run-id")
    parser.add_argument("--start-from", help="start a new recovery run from this node using hashed existing upstream artifacts")
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--provider", choices=("codex", "hermes"), default="codex")
    parser.add_argument("provider_command", nargs="*", help="optional Provider command override")
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    if args.provider == "codex":
        executor = CodexExecutor(root, command=args.provider_command or None, timeout=args.timeout)
        executor.preflight()
    else:
        if not args.provider_command:
            parser.error("Hermes requires a provider command")
        executor = HermesExecutor(args.provider_command, cwd=root, timeout=args.timeout)
    browser = PlaywrightBrowserEvidenceCollector(root)
    browser.preflight()
    state = WorkflowRunner(root, executor, browser).run(args.workflow, args.run_id, args.start_from)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0 if state["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
