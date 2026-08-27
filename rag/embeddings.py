from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol, Sequence


ASCII_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-_.][a-z0-9]+)*", re.IGNORECASE)
CJK_RUN_RE = re.compile(r"[\u3400-\u9fff]+")
SYNONYM_GROUPS = (
    ("用户", "客群", "受众", "消费者", "人群"),
    ("页面", "栏目", "站点地图", "导航", "界面"),
    ("下单", "购物车", "支付", "购买", "交易"),
    ("常见问题", "faq", "问答", "问题"),
    ("品牌", "定位", "调性", "形象"),
    ("香调", "前调", "中调", "后调", "气味"),
)
INTENT_PATTERNS = (
    (
        "sitemap",
        ("哪些页面", "页面有哪些", "页面清单", "站点地图", "信息架构", "导航必须包含", "站点需要"),
    ),
    ("audience", ("目标用户", "目标客群", "核心用户", "受众是谁")),
    ("commerce_boundary", ("在线下单", "在线支付", "购物车", "交易系统", "一期不提供")),
    ("faq_scope", ("faq需要", "faq 至少", "常见问题", "问题覆盖")),
    ("brand_position", ("品牌定位", "定位是什么", "品牌名称", "核心差异点")),
)


class EmbeddingProvider(Protocol):
    dimension: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class DeterministicFeatureEmbedding:
    """Reproducible local feature hashing; replaceable by a semantic provider."""

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> list[float]:
        normalized = text.casefold()
        features: list[tuple[str, float]] = []
        for token in ASCII_TOKEN_RE.findall(normalized):
            features.append((f"w:{token}", 1.8))
        for run in CJK_RUN_RE.findall(normalized):
            for n, weight in ((1, 0.35), (2, 1.2), (3, 1.6)):
                for index in range(max(0, len(run) - n + 1)):
                    features.append((f"c{n}:{run[index:index+n]}", weight))
        for group_index, terms in enumerate(SYNONYM_GROUPS):
            if any(term in normalized for term in terms):
                features.append((f"syn:{group_index}", 2.4))
        for intent, patterns in INTENT_PATTERNS:
            if any(pattern in normalized for pattern in patterns):
                features.append((f"intent:{intent}", 8.0))

        vector = [0.0] * self.dimension
        for feature, weight in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest, "big") % self.dimension
            sign = 1.0 if digest[0] & 1 else -1.0
            vector[bucket] += sign * weight
        norm = math.sqrt(sum(item * item for item in vector))
        if norm:
            vector = [item / norm for item in vector]
        return vector


def vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"
