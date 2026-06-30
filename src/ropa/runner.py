"""Result types + helpers shared by the admission scheduler.

A file runs as one `robot` subprocess; these helpers name its output file and
parse it back into per-test results.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from robot.api import ExecutionResult

from .discover import TestUnit


@dataclass
class TestResult:
    unit: TestUnit
    output_xml: Path
    status: str          # PASS / FAIL / ERROR
    seconds: float
    attempts: int = 1    # how many times it had to run
    flaky: bool = False  # failed at least once, then passed


def part_path(run_dir: Path, key: str) -> Path:
    """Stable output path keyed by name (not position), so retry passes that
    re-run only a subset don't overwrite each other's parts."""
    h = hashlib.md5(key.encode()).hexdigest()[:12]
    return (Path(run_dir) / f"out-{h}.xml").resolve()


def parse_file(out: Path, tests: list[TestUnit]) -> list[TestResult]:
    """Parse a worker's output.xml into per-test results; missing tests (the
    subprocess crashed before reaching them) become ERROR."""
    by_name = {u.name: u for u in tests}
    found: list[TestResult] = []
    seen: set[str] = set()
    if out.exists():
        try:
            result = ExecutionResult(str(out))

            def visit(suite):
                for test in suite.tests:
                    unit = by_name.get(test.name)
                    if unit is None:
                        continue
                    seen.add(unit.name)
                    found.append(TestResult(
                        unit=unit, output_xml=out, status=test.status,
                        seconds=test.elapsedtime / 1000.0))
                for sub in suite.suites:
                    visit(sub)

            visit(result.suite)
        except Exception:  # noqa: BLE001 - a broken output.xml is just ERRORs
            pass
    for unit in tests:
        if unit.name not in seen:
            found.append(TestResult(unit=unit, output_xml=out,
                                    status="ERROR", seconds=0.0))
    return found
