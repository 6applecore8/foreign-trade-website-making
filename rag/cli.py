from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import run_benchmark, write_report
from .pipeline import RagPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Requirement-document RAG for site generation")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db")
    subparsers.add_parser("health")

    ingest = subparsers.add_parser("ingest")
    ingest.add_argument("--project-key", required=True)
    ingest.add_argument("--document", required=True)

    ask = subparsers.add_parser("ask")
    ask.add_argument("--project-key", required=True)
    ask.add_argument("--query", required=True)
    ask.add_argument("--top-k", type=int, default=5)

    context = subparsers.add_parser("build-context")
    context.add_argument("--project-key", required=True)
    context.add_argument("--questions-file", required=True)
    context.add_argument("--output", required=True)
    context.add_argument("--top-k", type=int, default=5)

    benchmark = subparsers.add_parser("benchmark")
    benchmark.add_argument("--project-key", default="perfume-e2e")
    benchmark.add_argument("--document", required=True)
    benchmark.add_argument("--rounds", type=int, default=10)
    benchmark.add_argument("--output", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    pipeline = RagPipeline()
    if args.command == "init-db":
        pipeline.initialize()
        result = {"status": "initialized"}
    elif args.command == "health":
        result = pipeline.store.health()
    elif args.command == "ingest":
        result = pipeline.ingest(args.project_key, args.document)
    elif args.command == "ask":
        result = pipeline.ask(args.project_key, args.query, args.top_k).to_dict()
    elif args.command == "build-context":
        questions = json.loads(Path(args.questions_file).read_text(encoding="utf-8"))
        if not isinstance(questions, list) or not questions or not all(
            isinstance(item, str) and item.strip() for item in questions
        ):
            raise ValueError("questions file must be a non-empty JSON array of strings")
        result = {
            "schema_version": "1.0",
            "project_key": args.project_key,
            "trust": "untrusted_client_evidence",
            "context_packs": [
                pipeline.ask(args.project_key, question, args.top_k).to_dict()
                for question in questions
            ],
        }
        pipeline.config.ensure_runtime_dirs()
        allowed_output = pipeline.config.output_dir.resolve()
        target = Path(args.output).resolve()
        if target != allowed_output and allowed_output not in target.parents:
            raise ValueError("context output must stay inside rag-data/outputs")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    else:
        if args.rounds < 1:
            raise ValueError("rounds must be >= 1")
        result = run_benchmark(
            pipeline, args.document, args.project_key, rounds=args.rounds
        )
        write_report(result, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
