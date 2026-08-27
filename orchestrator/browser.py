from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .executor import ArtifactReceipt


class BrowserEvidenceCollector(ABC):
    """Collects real-browser desktop evidence; implementations may use any browser provider."""

    @abstractmethod
    def collect(
        self,
        site_dir: Path,
        evidence_path: Path,
        screenshot_path: Path,
        viewport: tuple[int, int] = (1440, 900),
    ) -> ArtifactReceipt:
        raise NotImplementedError
