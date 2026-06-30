"""Per-test runtime history — the data that lets ropa beat pabot on stragglers.

We persist how long each test took last time (keyed by longname) so the
scheduler can run the slowest tests first (longest-processing-time first),
which minimizes the makespan — the finish time of the last worker.

pabot has no equivalent: it orders by name, blind to actual cost.
"""

from __future__ import annotations

import json
from pathlib import Path


class History:
    def __init__(self, path: str | Path = ".ropa/history.json") -> None:
        self.path = Path(path)
        self._times: dict[str, float] = {}
        if self.path.exists():
            try:
                self._times = json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError):
                self._times = {}

    def duration(self, longname: str, default: float = 0.0) -> float:
        """Last known duration in seconds; `default` for never-seen tests."""
        return self._times.get(longname, default)

    def record(self, longname: str, seconds: float) -> None:
        # Exponential moving average smooths out one-off blips.
        prev = self._times.get(longname)
        self._times[longname] = seconds if prev is None else 0.5 * prev + 0.5 * seconds

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._times, indent=0, sort_keys=True))
