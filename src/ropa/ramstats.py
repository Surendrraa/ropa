"""Per-file RAM accounting — the data the admission scheduler packs against.

Each .robot file runs as its own subprocess, so we measure the peak RSS of *that
file's* whole process tree (robot + node + browser) cleanly and attribute it to
the file. We persist an EMA-smoothed per-file MB so the credit scheduler packs
against real costs (heavy files reserve more credits, light files pack densely)
and gets more accurate every run. Measurement is cross-platform via psutil.
"""

from __future__ import annotations

import json
from pathlib import Path

import psutil


def tree_rss_mb(pid: int) -> int:
    """Sum RSS (MB) of a process and all its descendants — a file's whole tree."""
    total = 0
    try:
        proc = psutil.Process(pid)
        procs = [proc, *proc.children(recursive=True)]
    except psutil.Error:
        return 0
    for p in procs:
        try:
            total += p.memory_info().rss
        except psutil.Error:
            continue
    return total // (1024 * 1024)


class RamStats:
    """Persisted per-file RAM costs (MB), EMA-smoothed, with a global fallback."""

    def __init__(self, path: str | Path = ".ropa/ram.json") -> None:
        self.path = Path(path)
        self.global_mb: int | None = None
        self.files: dict[str, int] = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                self.global_mb = data.get("global_mb")
                self.files = data.get("files", {})
            except (json.JSONDecodeError, OSError):
                pass

    def cost(self, source: str, default: int) -> int:
        """Predicted RAM for a file: its learned cost, else global, else default."""
        return self.files.get(source) or self.global_mb or default

    def record(self, source: str, peak_mb: int) -> None:
        if peak_mb <= 0:
            return
        prev = self.files.get(source)
        self.files[source] = round(peak_mb if prev is None
                                   else 0.5 * prev + 0.5 * peak_mb)
        # Keep a global average as the fallback for never-seen files.
        vals = list(self.files.values())
        self.global_mb = round(sum(vals) / len(vals))

    def save(self) -> None:
        if not self.files:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(
            {"global_mb": self.global_mb, "files": self.files}, indent=0))
