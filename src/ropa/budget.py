"""RAM helpers for the memory-credit admission scheduler.

Measured fact: browser RAM scales ~linearly with the number of CONCURRENT files,
and sharing browser *engines* does not reduce it (the cost is the rendered page).
So the only reliable way to bound peak RAM is to bound concurrency — which the
admission scheduler does by admitting files only while they fit a RAM budget.
"""

from __future__ import annotations

import psutil


def available_ram_mb() -> int:
    """Available RAM in MB (cross-platform via psutil)."""
    try:
        return psutil.virtual_memory().available // (1024 * 1024)
    except Exception:  # noqa: BLE001 - never let memory probing crash a run
        return 0


def total_ram_mb() -> int:
    """Total physical RAM in MB (cross-platform via psutil)."""
    try:
        return psutil.virtual_memory().total // (1024 * 1024)
    except Exception:  # noqa: BLE001
        return 0


def parse_ram(text: str | None) -> int | None:
    """Parse '4G' / '4096M' / '4096' (MB) into an int number of MB."""
    if not text:
        return None
    s = text.strip().upper().rstrip("B")
    mult = 1
    if s.endswith("G"):
        mult, s = 1024, s[:-1]
    elif s.endswith("M"):
        mult, s = 1, s[:-1]
    return int(float(s) * mult)
