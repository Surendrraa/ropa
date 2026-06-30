#!/usr/bin/env python3
"""Benchmark ropa vs pabot on the same suite: wall-clock + peak RAM.

Why a custom sampler instead of `/usr/bin/time`: ropa runs its browser in a
*separate* session (so it can clean it up), and pabot spawns browsers inside its
own tree. `/usr/bin/time -v` only sees the direct child, so it would undercount
one side. Here we sample RSS system-wide across all test/browser processes and
subtract a pre-launch baseline — the same rule for both, so the comparison is
fair.

Usage:
    python bench/compare.py examples/web_many.robot --processes 4
    python bench/compare.py path/to/your/real/suite --processes 8
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
import time

PAGE = os.sysconf("SC_PAGE_SIZE")
# Processes that belong to a parallel Robot run (either tool).
MATCH = re.compile(r"chromium|headless_shell|chrome_crashpad|node|playwright|"
                   r"pabot|ropa|robot|/python")


def total_rss_bytes() -> int:
    """Sum RSS of every process whose cmdline looks like a test/browser proc."""
    total = 0
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().replace(b"\x00", b" ").decode("utf-8", "ignore")
            if not MATCH.search(cmd):
                continue
            with open(f"/proc/{pid}/statm") as f:
                rss_pages = int(f.read().split()[1])
            total += rss_pages * PAGE
        except (FileNotFoundError, ProcessLookupError, PermissionError, IndexError):
            continue
    return total


def run_sampled(cmd: list[str], env: dict | None = None) -> tuple[float, int, int]:
    """Run cmd, sampling peak RSS. Returns (wall_seconds, peak_delta_bytes, rc)."""
    baseline = total_rss_bytes()
    peak = baseline
    start = time.monotonic()
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    while proc.poll() is None:
        peak = max(peak, total_rss_bytes())
        time.sleep(0.2)
    wall = time.monotonic() - start
    return wall, max(0, peak - baseline), proc.returncode


def mb(n: int) -> str:
    return f"{n / 1024 / 1024:6.0f} MB"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("suite", nargs="+", help="Suite files/dirs to run.")
    ap.add_argument("-p", "--processes", type=int, default=4)
    ap.add_argument("--no-browser", action="store_true",
                    help="Suites don't use the Browser library (skip shared "
                         "Node / testlevelsplit browser tuning).")
    ap.add_argument("--runs", type=int, default=1,
                    help="Repeat each tool N times and report the best wall.")
    ap.add_argument("--pabot-extra", default="",
                    help="Extra args appended to the pabot command, quoted, "
                         "e.g. --pabot-extra='--suitestatlevel 2'.")
    ap.add_argument("--ropa-extra", default="",
                    help="Extra args appended to the ropa command.")
    args = ap.parse_args()

    src_env = dict(os.environ, PYTHONPATH="src")
    browser = not args.no_browser

    # --testlevelsplit so pabot parallelizes tests within a single suite too,
    # matching ropa's test-level parallelism (apples to apples).
    pabot_cmd = ["pabot", "--processes", str(args.processes)]
    if browser:
        pabot_cmd.append("--testlevelsplit")
    pabot_cmd += shlex.split(args.pabot_extra)
    pabot_cmd += ["--outputdir", "/tmp/bench_pabot", *args.suite]

    ropa_cmd = [sys.executable, "-m", "ropa.cli", "-p", str(args.processes)]
    ropa_cmd += shlex.split(args.ropa_extra)
    ropa_cmd += ["-d", "/tmp/bench_ropa", *args.suite]

    print(f"suite={args.suite}  processes={args.processes}  "
          f"browser={browser}  runs={args.runs}\n")
    print(f"{'tool':<10}{'best wall':>11}{'peak RAM':>14}{'rc':>5}")
    print("-" * 40)
    rows = []
    for name, cmd in (("pabot", pabot_cmd), ("ropa", ropa_cmd)):
        best_wall, peak_at_best, last_rc = None, 0, 0
        for _ in range(max(1, args.runs)):
            time.sleep(1)  # let things settle between runs
            wall, peak, last_rc = run_sampled(cmd, env=src_env)
            if best_wall is None or wall < best_wall:
                best_wall, peak_at_best = wall, peak
        rows.append((name, best_wall, peak_at_best))
        print(f"{name:<10}{best_wall:>10.1f}s{mb(peak_at_best):>14}{last_rc:>5}")

    (_, pw, pr), (_, rw, rr) = rows
    print("\nropa vs pabot:")
    if pw and rw:
        print(f"  wall-clock : {pw / rw:.2f}x  faster" if rw < pw
              else f"  wall-clock : {rw / pw:.2f}x slower")
    if pr and rr:
        print(f"  peak RAM   : {pr / rr:.2f}x  less" if rr < pr
              else f"  peak RAM   : {rr / pr:.2f}x more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
