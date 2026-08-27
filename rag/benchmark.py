from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from .pipeline import RagPipeline


CASES = (
    {
        "query": "香水品牌名称和定位是什么？",
        "expected_all": ("AURELIA NO.7", "现代法式香氛"),
    },
    {
        "query": "这个独立站的目标用户是谁？",
        "expected_all": ("24–38", "一二线城市"),
    },
    {
        "query": "独立站需要建设哪些页面？",
        "expected_all": ("女士香水", "中性香水", "香调指南"),
    },
    {
        "query": "第一阶段支持购物车、在线下单和支付吗？",
        "expected_all": ("不提供购物车", "不提供在线支付"),
    },
    {
        "query": "FAQ需要覆盖哪些问题？",
        "expected_all": ("留香", "试香", "退换"),
    },
)


def run_benchmark(
    pipeline: RagPipeline,
    source: str | Path,
    project_key: str,
    rounds: int = 10,
) -> dict[str, object]:
    ingest_result = pipeline.ingest(project_key, source)
    for case in CASES:
        pipeline.ask(project_key, case["query"], top_k=3)

    timings: list[float] = []
    case_results = []
    for case in CASES:
        first_pack = None
        for _ in range(rounds):
            pack = pipeline.ask(project_key, case["query"], top_k=3)
            timings.append(pack.retrieval_ms)
            first_pack = first_pack or pack
        combined = "\n".join(hit.content for hit in first_pack.results)
        matched = [value for value in case["expected_all"] if value in combined]
        correct = len(matched) == len(case["expected_all"])
        case_results.append(
            {
                "query": case["query"],
                "expected_all": list(case["expected_all"]),
                "matched": matched,
                "correct_top3": correct,
                "selected_layer": first_pack.selected_layer,
                "top_sources": [hit.source_ref for hit in first_pack.results],
                "sample_retrieval_ms": round(first_pack.retrieval_ms, 3),
            }
        )

    ordered = sorted(timings)
    p95_index = max(0, min(len(ordered) - 1, int(0.95 * len(ordered) + 0.999999) - 1))
    correct_count = sum(1 for item in case_results if item["correct_top3"])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "PostgreSQL/pgvector hybrid retrieval only; excludes external LLM generation",
        "project_key": project_key,
        "ingest": ingest_result,
        "queries": len(CASES),
        "rounds_per_query": rounds,
        "measurements": len(timings),
        "correct_top3": correct_count,
        "correctness_rate": round(correct_count / len(CASES), 4),
        "latency_ms": {
            "min": round(min(timings), 3),
            "mean": round(statistics.fmean(timings), 3),
            "p50": round(statistics.median(timings), 3),
            "p95": round(ordered[p95_index], 3),
            "max": round(max(timings), 3),
        },
        "cases": case_results,
    }


def write_report(report: dict[str, object], output: str | Path) -> None:
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
