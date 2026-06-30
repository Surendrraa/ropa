# ropa

A **memory-safe parallel runner for Robot Framework + Browser (Playwright)** — a
`pabot` alternative built for one fixed machine: run as many `.robot` files in
parallel as the RAM allows, queue the rest, **never OOM**.

## Install

`ropa` installs once on your machine and works in **every** Robot Framework
project — like `pabot`. No per-project setup.

```bash
# recommended: isolated CLI install (needs pipx; cross-platform)
pipx install "git+https://github.com/Surendrraa/ropa.git"

# or plain pip (user install)
pip install --user "git+https://github.com/Surendrraa/ropa.git"
```

Verify:

```bash
ropa --version      # ropa 0.1.0
ropa --help
```

Upgrade later:

```bash
pipx upgrade ropa            # if installed with pipx
pip install --user -U "git+https://github.com/Surendrraa/ropa.git"   # if pip
```

Requires Python ≥ 3.10. Browser tests also need `robotframework-browser`
(`pip install robotframework-browser && rfbrowser init`) in your project.

## Run

From any project's root:

```bash
ropa -p 8 --max-ram 12G tests/
ropa -p 8 --max-ram 12G --retry 1 tests/        # auto-retry flaky files
ropa -p 8 --max-ram 12G -i smoke tests/         # only the 'smoke' tag
```

Outputs standard `output.xml` + `log.html` + `report.html` in `ropa_results/`.
Per-project learning lives in `.ropa/` (add it to your project's `.gitignore`).

## The model

- A **`.robot` file is the atomic unit.** Its tests run sequentially (case 2 may
  depend on case 1); the file imports only resource files, never another
  `.robot`, so files are independent. **Files run in parallel; a file is never
  split across workers.**
- **RAM law (measured):** `peak RAM ≈ concurrency × rendered-page RAM`. Sharing
  browser engines does *not* reduce it — the cost is the rendered page, not the
  engine. So the only reliable lever is **bounding concurrency to fit RAM**.

## How it stays within RAM — memory-credit admission control

The standard resource-scheduler pattern (Kubernetes / Nomad / Slurm), applied to
test files:

- Each file is a **job with a RAM cost** (learned per file, `.ropa/ram.json`).
- A file is **admitted only when** it fits the remaining budget **and** live free
  RAM is above the floor **and** it's under the concurrency cap.
- When a file finishes it **releases its credits** and the next waiting file
  starts. It is impossible to OOM — work that doesn't fit is never admitted.
- Each file runs as its **own subprocess in its own session**, so ropa measures
  the peak RAM of *that file's whole tree* and feeds it back — **packing
  self-tunes every run** (heavy files reserve more, light files pack densely).

```
-p N         max files running at once (cap)
--max-ram    RAM budget for concurrent files (default: 80% of available)
--min-free   live free-RAM floor, never crossed (default: 1024 MB)
--retry N    re-run whole failing FILES; pass-on-retry => reported flaky
```

Tight budget → files run in waves (reliable, slower). Loose budget → more in
parallel. Either way: full-fidelity real browsers, no OOM, standard reports.

## Verified

- Gating: tight budget serializes, loose budget parallelizes (same files).
- Retry at file granularity; merged report has correct de-duplicated counts.
- Per-file RAM measured and learned across runs.

## Benchmark vs pabot

```bash
python bench/compare.py path/to/tests -p 8 --runs 3
```

Measure on the real target machine — browser RAM/timing on a constrained dev box
is noisy.

## Roadmap

- Makespan / auto-`-p` oracle from learned per-file time + RAM.
- Test-impact selection: run only files a code change can affect.
