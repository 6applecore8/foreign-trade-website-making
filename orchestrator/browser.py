from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
import shutil
import subprocess

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


class PlaywrightBrowserEvidenceCollector(BrowserEvidenceCollector):
    """Collect desktop evidence with system Edge/Chrome through playwright-core."""

    BROWSER_CANDIDATES = (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    )

    def __init__(self, project_root: Path, *, node_command: str | None = None,
                 browser_executable: Path | None = None, timeout: float = 60.0):
        self.project_root = Path(project_root).resolve(strict=True)
        self.node_command = node_command or shutil.which("node") or ""
        self.browser_executable = Path(browser_executable) if browser_executable else next(
            (candidate for candidate in self.BROWSER_CANDIDATES if candidate.is_file()), Path()
        )
        self.timeout = timeout

    def preflight(self) -> None:
        if not self.node_command:
            raise RuntimeError("Node.js is required for desktop browser evidence collection")
        if not self.browser_executable.is_file():
            raise RuntimeError("Microsoft Edge or Google Chrome is required for desktop browser evidence collection")
        script = self.project_root / "scripts" / "collect_browser_evidence.mjs"
        if not script.is_file():
            raise RuntimeError(f"browser evidence script is missing: {script}")
        dependency = self.project_root / "intake" / "node_modules" / "playwright-core"
        if not dependency.is_dir():
            raise RuntimeError("playwright-core is missing; run npm install in intake/")

    def collect(
        self,
        site_dir: Path,
        evidence_path: Path,
        screenshot_path: Path,
        viewport: tuple[int, int] = (1440, 900),
    ) -> ArtifactReceipt:
        if viewport != (1440, 900):
            return ArtifactReceipt("desktop-browser-validation", "failed", detail="only the 1440x900 desktop contract is supported")
        try:
            self.preflight()
            script = self.project_root / "scripts" / "collect_browser_evidence.mjs"
            result = subprocess.run(
                [
                    self.node_command,
                    str(script),
                    str(Path(site_dir).resolve(strict=True)),
                    str(Path(evidence_path).resolve()),
                    str(Path(screenshot_path).resolve()),
                    str(self.browser_executable.resolve(strict=True)),
                    str(self.project_root),
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            return ArtifactReceipt("desktop-browser-validation", "failed", detail=str(error))
        if result.returncode != 0:
            return ArtifactReceipt(
                "desktop-browser-validation", "failed",
                detail=result.stderr.strip() or f"browser collector exited {result.returncode}",
            )
        return ArtifactReceipt(
            "desktop-browser-validation", "success",
            artifacts=[str(evidence_path), str(screenshot_path)],
        )
