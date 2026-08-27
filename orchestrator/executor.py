from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExecutionRequest:
    node_id: str
    prompt_version: str
    execution_root: Path
    prompt_path: Path
    input_artifacts: tuple[Path, ...]
    allowed_read_paths: tuple[Path, ...]
    allowed_write_paths: tuple[Path, ...]
    output_schema: dict[str, Any] | None = None
    untrusted_inputs: tuple[Path, ...] = ()


@dataclass
class ArtifactReceipt:
    node_id: str
    status: str
    artifacts: list[str] = field(default_factory=list)
    hashes: dict[str, str] = field(default_factory=dict)
    detail: str = ""


class AgentExecutor(ABC):
    """Provider-neutral boundary. Implementations may call Hermes or another model."""

    @abstractmethod
    def run_agent(self, request: ExecutionRequest) -> ArtifactReceipt:
        raise NotImplementedError
