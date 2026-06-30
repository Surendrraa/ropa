# ropa

A **memory-safe parallel runner for Robot Framework + Browser (Playwright)** — a
`pabot` alternative built for one fixed machine: run as many `.robot` files in
parallel as the RAM allows, queue the rest, **never OOM**.

## Install

`ropa` runs `robot` for you, so it must live in the **same environment as your
Robot Framework + Browser library** (just like `pabot`). Install it next to your
test dependencies — **do not** `pipx`-isolate it (an isolated venv won't have your
Browser library or project libraries, so your tests would fail to import them).

**Recommended — a project virtual environment (zero risk to system packages):**

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install robotframework robotframework-browser
rfbrowser init                     # installs the Playwright browsers
pip install "git+https://github.com/Surendrraa/ropa.git"
```

**Or into your existing user environment** (where `robotframework` already is):

```bash
pip install --user "git+https://github.com/Surendrraa/ropa.git"
# If your OS Python is "externally managed" (PEP 668) and you are NOT in a venv,
# pip refuses with a warning. Prefer a venv (above) — it avoids this entirely.
# Only as a last resort add: --break-system-packages
```

Verify:

```bash
ropa --version      # ropa 0.1.0
ropa --help
```

Requires Python ≥ 3.10. A virtual environment never touches system packages, so
it is the safe and recommended path.

## Run

From any project's root:

```bash
ropa -p 8 --max-ram 12G tests/
ropa -p 8 --max-ram 12G --retry 1 tests/        # auto-retry flaky files
ropa -p 8 --max-ram 12G -i smoke tests/         # only the 'smoke' tag
```

Outputs standard `output.xml` + `log.html` + `report.html` in `ropa_results/`.
Per-project learning lives in `.ropa/` (add it to your project's `.gitignore`).

## CI/CD (drop-in for pabot)

Same slot as `robotframework-pabot`, one-line command swap, exits non-zero on
failures. Set `--max-ram` to the runner's RAM minus ~1 GB so it can't OOM:

```diff
- pabot --processes 4           --outputdir reports tests
+ ropa  -p 4   --max-ram 7G     --outputdir reports tests   # 8 GB runner
```

Full Bitbucket Pipelines + GitHub Actions examples: **[docs/ci.md](docs/ci.md)**.

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
