"""Merge worker output.xml files into the standard Robot reports.

Each attempt produces several *disjoint* chunk outputs (one per worker). We
combine each attempt into a single xml, then apply retry semantics ourselves on
the result model: the first attempt is the canonical tree (it has every test),
and each later attempt overrides the matching test's result. Doing the override
manually (keyed by test name) avoids rebot's fragile cross-tree merge, which
duplicated retried tests once the parallel chunk structure differed between
attempts.

Produces the usual `output.xml` + `log.html` + `report.html` — drop-in for
existing CI and report tooling. Assumes test names are unique across the run
(standard Robot practice; our suites use unique TC ids).
"""

from __future__ import annotations

from pathlib import Path

from robot.api import ExecutionResult
from robot.reporting import ResultWriter

from robot import rebot


def _combine_attempt(files: list[Path], out: Path, name: str) -> bool:
    existing = [str(p) for p in files if p.exists()]
    if not existing:
        return False
    rebot(*existing, output=str(out), log=None, report=None, name=name,
          merge=False)
    return True


def _index_tests(suite, into: dict) -> None:
    for test in suite.tests:
        into[test.name] = test
    for sub in suite.suites:
        _index_tests(sub, into)


def merge(attempt_files: list[list[Path]], outputdir: Path,
          name: str = "ropa") -> int:
    outputdir.mkdir(parents=True, exist_ok=True)
    combine_dir = outputdir / "parts"
    combine_dir.mkdir(parents=True, exist_ok=True)

    combined: list[Path] = []
    for i, files in enumerate(attempt_files):
        out = combine_dir / f"attempt-{i}.xml"
        if _combine_attempt(files, out, name):
            combined.append(out)
    if not combined:
        return 252

    base = ExecutionResult(str(combined[0]))
    base_tests: dict = {}
    _index_tests(base.suite, base_tests)

    # Apply each retry attempt over the base (latest result wins).
    for path in combined[1:]:
        rerun = ExecutionResult(str(path))
        rerun_tests: dict = {}
        _index_tests(rerun.suite, rerun_tests)
        for tname, rtest in rerun_tests.items():
            btest = base_tests.get(tname)
            if btest is None:
                continue
            btest.status = rtest.status
            btest.message = rtest.message
            btest.starttime = rtest.starttime
            btest.endtime = rtest.endtime
            btest.body = rtest.body

    writer = ResultWriter(base)
    writer.write_results(
        output=str(outputdir / "output.xml"),
        log=str(outputdir / "log.html"),
        report=str(outputdir / "report.html"),
    )
    return base.return_code
