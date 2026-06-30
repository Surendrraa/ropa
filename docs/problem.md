# ropa — why it exists (the real problems with pabot)

Stack we target: **Robot Framework + Browser library (Playwright)**, run in parallel.
Today that means `pabot`. Here is exactly what pabot does and where it leaks
time, RAM and CPU — each item is a concrete thing ropa fixes.

## How pabot runs (so the problems make sense)
1. Splits suites (by suite, or by test with `--testlevelsplit`).
2. Spawns N **fresh** `robot` subprocesses (`--processes N`), each a new Python
   interpreter writing its **own** `output.xml`.
3. Optional **PabotLib** XML-RPC server for locks / value sets.
4. At the end, `rebot` **merges** every `output.xml` into the final report.

## The real problems

### P1 — Stragglers (tail latency)
Split is decided **upfront and statically**. One heavy suite pins a core while
the rest sit idle. A finished worker **cannot steal** work from a busy one.
→ ropa: **work-stealing queue** + **history-aware longest-first** scheduling.

### P2 — Suite Setup/Teardown runs N times
`--testlevelsplit` makes `Suite Setup` run **once per process** that got a slice.
Expensive setups (login, DB seed, `New Browser`) get paid 8x.
→ ropa: setup-aware grouping; amortize setup across a worker's tests.

### P3 — Fresh interpreter per process = re-import + browser re-launch
Each subprocess re-imports RF + libraries and re-parses suites (2-4s) before any
test runs. Stateful libs can't share anything (separate interpreters).
→ ropa: warm worker pool (paid once), shared resources.

### P4 — Playwright-specific: one Node server + one full browser PER process
The Browser library starts its **own Playwright Node server** and launches its
**own full browser** in every `robot` process. 8 parallel = 8 Node servers +
8 browsers (~300 MB each). This is the RAM blowup that caps your concurrency.
→ ropa: **shared Playwright browser + one BrowserContext per parallel unit**
   (context ~10-40 MB vs ~300 MB browser) → ~5-10x more parallel tests / GB.

### P5 — `rebot` merge is a single-threaded end-of-run wall
Merging GB-scale `output.xml` files in memory at the end → CPU + RAM spike,
OOM risk in CI.
→ ropa: stream/fold each result as it finishes; bounded memory.

### P6 — Static `--processes N`, no resource awareness
No CPU/mem feedback → oversubscribe and thrash, or undersubscribe and idle.
→ ropa: adaptive concurrency (later phase).

### P7 — No native flaky retry
`--rerunfailed` is a separate full pass + manual `rebot --merge`.
→ ropa: inline isolated single-test retry + flake quarantine (later phase).

### P8 — Hidden ordering dependencies surface as "flakes"
Tests implicitly depend on order/global state; parallel run breaks them
non-deterministically.
→ ropa: dependency hints + shuffle-based coupling detector (later phase).

## Output
ropa emits **standard Robot Framework `output.xml` + `log.html` + `report.html`**
(via rebot) — no traces/videos required. Drop-in with existing CI/reports.
