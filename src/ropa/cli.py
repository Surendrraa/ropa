"""ropa command-line entry point.

    ropa --processes 8 tests/

Drop-in-ish with pabot: point it at suite paths, choose a worker count, get the
standard Robot reports out — but scheduled by runtime history with a
work-stealing pool instead of a static split.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import __version__
from .admission import run_files
from .budget import available_ram_mb, parse_ram
from .discover import discover
from .history import History
from .merge import merge
from .ramstats import RamStats


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ropa", description=__doc__)
    p.add_argument("paths", nargs="+", help="Suite files or directories to run.")
    p.add_argument("-p", "--processes", type=int, default=4,
                   help="Number of parallel workers (default: 4).")
    p.add_argument("-d", "--outputdir", default="ropa_results",
                   help="Directory for the final reports (default: ropa_results).")
    p.add_argument("-i", "--include", action="append", default=[],
                   help="Only run tests with these tags (repeatable).")
    p.add_argument("-e", "--exclude", action="append", default=[],
                   help="Skip tests with these tags (repeatable).")
    p.add_argument("--history", default=".ropa/history.json",
                   help="Path to the runtime-history file.")
    p.add_argument("--max-ram", metavar="SIZE",
                   help="RAM budget for concurrent files (e.g. 12G, 8192M). "
                        "The credit scheduler admits files only while they fit, "
                        "so it never OOMs. Default: 80%% of available RAM.")
    p.add_argument("--min-free", type=int, default=1024, metavar="MB",
                   help="Live free-RAM floor: never admit a file if it would "
                        "push MemAvailable below this (default: 1024).")
    p.add_argument("--retry", type=int, default=0, metavar="N",
                   help="Re-run each failing test up to N times; a test that "
                        "then passes is reported as flaky (default: 0).")
    p.add_argument("--version", action="version", version=f"ropa {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    units = discover(args.paths, includes=args.include, excludes=args.exclude)
    if not units:
        print("ropa: no tests found.", file=sys.stderr)
        return 252

    # Group tests by .robot file — the atomic unit (file = one job).
    files: dict[str, list] = {}
    for u in units:
        files.setdefault(u.source, []).append(u)
    file_list = list(files.items())
    total = len(units)

    ram_stats = RamStats(str(Path(args.history).parent / "ram.json"))
    budget_mb = parse_ram(args.max_ram) or int(available_ram_mb() * 0.8)
    cold_default = 1000  # MB assumed for a never-seen file (conservative)

    def cost_fn(source: str) -> int:
        return ram_stats.cost(source, cold_default)

    print(f"ropa {__version__}: {total} tests in {len(file_list)} files | "
          f"budget {budget_mb}MB, keep {args.min_free}MB free, "
          f"≤{args.processes} concurrent")

    history = History(args.history)
    outputdir = Path(args.outputdir)
    run_dir = outputdir / "parts"
    wall_start = time.monotonic()
    peak_seen = 0

    def progress(res, peak_mb):
        nonlocal peak_seen
        peak_seen = max(peak_seen, peak_mb)
        history.record(res.unit.longname, res.seconds)
        print(f"  {res.status:<5} {res.seconds:6.1f}s  {res.unit.longname}")

    # Inline flaky-retry (P7) at FILE granularity: re-run whole files that had
    # any failure (in-file tests are sequential and may depend on each other).
    final: dict[str, object] = {}
    attempt_files: list[list[Path]] = []
    pending = file_list
    attempt = 1
    max_attempts = args.retry + 1
    while pending and attempt <= max_attempts:
        label = "run" if attempt == 1 else f"retry {attempt - 1}"
        print(f"\n[{label}] {len(pending)} files")
        results, measured = run_files(
            pending, run_dir / f"a{attempt}",
            budget_mb=budget_mb, floor_mb=args.min_free,
            max_procs=args.processes, cost_fn=cost_fn, on_result=progress)
        for src, mb in measured.items():
            ram_stats.record(src, mb)
        for res in results:
            res.attempts = attempt
            res.flaky = res.status == "PASS" and attempt > 1
            final[res.unit.longname] = res
        attempt_files.append(sorted({r.output_xml for r in results}))
        failed_sources = {r.unit.source for r in final.values()
                          if r.status != "PASS"}
        pending = [(s, u) for (s, u) in file_list if s in failed_sources]
        attempt += 1

    history.save()
    ram_stats.save()

    results = list(final.values())
    rc = merge(attempt_files, outputdir)

    failed = sum(1 for r in results if r.status != "PASS")
    flaky = sum(1 for r in results if r.flaky)
    wall = time.monotonic() - wall_start
    flaky_note = f", {flaky} flaky" if flaky else ""
    ram_note = f"  peak RAM {peak_seen}MB" if peak_seen else ""
    print(f"\nropa done in {wall:.1f}s — {total - failed} passed, "
          f"{failed} failed{flaky_note}.{ram_note}\n  Report: "
          f"{outputdir / 'report.html'}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
