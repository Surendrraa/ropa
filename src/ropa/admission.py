"""Memory-credit admission scheduler — run as many files as fit, queue the rest.

Standard resource-aware scheduling (the pattern Kubernetes/Nomad/Slurm use):
each .robot file is a job with a RAM cost; the scheduler admits a file only when
it fits the remaining budget AND the live free memory is above a floor. When a
file finishes it releases its credits and the next waiting file starts. It is
therefore impossible to OOM — we never admit work that doesn't fit.

Each file runs in its own session so we can measure the peak RSS of *its* tree
and feed that back into the per-file cost (RamStats), so packing self-tunes.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

from .budget import available_ram_mb
from .discover import TestUnit
from .ramstats import tree_rss_mb
from .runner import TestResult, parse_file, part_path


def run_files(files: list[tuple[str, list[TestUnit]]], run_dir: Path,
              budget_mb: int, floor_mb: int, max_procs: int,
              cost_fn, extra_args: list[str] | None = None,
              on_result=None) -> tuple[list[TestResult], dict[str, int]]:
    """Run files under a memory-credit budget. Returns (results, measured_mb)."""
    extra_args = extra_args or []
    run_dir.mkdir(parents=True, exist_ok=True)

    # Heaviest predicted first → better packing (classic LPT/first-fit-decreasing).
    pending = sorted(files, key=lambda f: cost_fn(f[0]), reverse=True)
    results: list[TestResult] = []
    measured: dict[str, int] = {}

    cv = threading.Condition()
    used_credits = 0
    running = 0

    def run_one(source: str, units: list[TestUnit]) -> None:
        nonlocal used_credits, running
        out = part_path(run_dir, source)
        cmd = [sys.executable, "-m", "robot", "--name", "ropa",
               "--output", str(out), "--log", "NONE", "--report", "NONE",
               "--console", "none", *extra_args, source]
        # Own session so the whole browser tree is contained and cleaned up.
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)
        peak = 0
        while proc.poll() is None:
            peak = max(peak, tree_rss_mb(proc.pid))
            time.sleep(0.2)
        file_results = parse_file(out, units)
        with cv:
            used_credits -= cost_fn(source)
            running -= 1
            measured[source] = max(peak, measured.get(source, 0))
            results.extend(file_results)
            if on_result:
                for r in file_results:
                    on_result(r, peak)
            cv.notify_all()

    threads: list[threading.Thread] = []
    with cv:
        while pending or running > 0:
            admitted = False
            for i, (source, units) in enumerate(pending):
                cost = cost_fn(source)
                # Two independent gates:
                #  - credit budget (predicted): the file's cost fits remaining
                #    credits and we're under the concurrency cap;
                #  - live backstop (measured): the box isn't already below the
                #    free-RAM floor.
                # Always allow one file to run alone (no deadlock if a single
                # file's predicted cost exceeds the whole budget).
                fits = used_credits + cost <= budget_mb and running < max_procs
                has_headroom = available_ram_mb() >= floor_mb
                if (running == 0) or (fits and has_headroom):
                    pending.pop(i)
                    used_credits += cost
                    running += 1
                    t = threading.Thread(target=run_one, args=(source, units),
                                         daemon=True)
                    threads.append(t)
                    t.start()
                    admitted = True
                    break
            if not admitted:
                cv.wait(timeout=1.0)  # wait for a slot to free or memory to recover

    for t in threads:
        t.join()
    return results, measured
