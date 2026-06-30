# ropa — Features, Comparison, and Roadmap

ropa is a memory-safe parallel runner for **Robot Framework + Browser
(Playwright)**, designed for one fixed machine (e.g. a single 16 GB box): run as
many `.robot` files in parallel as the RAM allows, queue the rest, **never OOM**.

Every feature below is framed as the **problem** it solves and the **solution**
(which is the feature). Everything in Part 1 is implemented and verified.

---

# Part 1 — Feature list (implemented)

### 1. File is the atomic unit of parallelism
- **Problem:** Test-level splitting (e.g. pabot `--testlevelsplit`) tears a
  `.robot` file apart. But inside a file, tests run sequentially and case 2 often
  depends on case 1 (login → add to cart → checkout). Split across workers, they
  run out of order or lose shared state → non-deterministic "flaky" failures that
  are really ordering bugs.
- **Solution:** ropa treats the **`.robot` file as the atomic unit**. A whole
  file always runs on one worker, its tests in order; files (which are
  independent — they import only resource files, never another `.robot`) run in
  parallel. In-file order is never broken.

### 2. Memory-credit admission control (never OOM)
- **Problem:** pabot takes a fixed `--processes N` that you guess by hand, blind
  to memory. If N browsers don't fit in RAM, the machine OOMs / swaps / thrashes
  and the run dies. (Observed: pabot `--testlevelsplit` on a real suite → 313 s,
  12 failures from memory pressure.)
- **Solution:** Each file is a **job with a RAM cost**. A scheduler admits a file
  only when `used_credits + cost ≤ budget`. When a file finishes it releases its
  credits and the next waiting file starts. Concurrency **floats** to fit the
  budget — work that doesn't fit is never started, so it is **impossible to OOM**.
  This is the standard resource-scheduler pattern (Kubernetes / Nomad / Slurm)
  applied to test files.

### 3. Live free-RAM backstop
- **Problem:** A RAM prediction can be wrong, and other processes on the box
  consume memory too. Pure accounting could still drift the machine into swap.
- **Solution:** A second, **measured** gate: before admitting a file, ropa
  checks live `MemAvailable` against a floor (`--min-free`, default 1024 MB) and
  refuses to admit if the box is already below it. Prediction + live measurement
  = no surprise OOM.

### 4. Per-file RAM learning (self-tuning packing)
- **Problem:** You don't know each file's RAM cost up front, and a flat per-file
  guess is wrong — a 20-context page test costs far more than a simple form test.
- **Solution:** Each file runs as **its own subprocess in its own OS session**, so
  ropa measures the peak RSS of *that file's whole tree* (robot + node +
  browser) and attributes it to the file. Costs are persisted EMA-smoothed in
  `.ropa/ram.json`. Heavy files reserve more credits, light files pack densely,
  and the packing gets **more accurate every run**.

### 5. Runtime-history scheduling (no straggler tail)
- **Problem:** Naive ordering can leave the slowest file running alone at the end
  while every other worker sits idle — the run is gated by one straggler.
- **Solution:** Per-test runtime is recorded (`.ropa/history.json`) and files
  are dispatched **heaviest-first** (first-fit-decreasing), so big files start
  early and the run finishes closer to its theoretical minimum (makespan).

### 6. Inline flaky-retry
- **Problem:** pabot has **no built-in retry**. Retrying failures means a manual,
  multi-step `pabot --rerunfailed output.xml` then `rebot --merge` — and it can't
  tell a genuine failure from a flaky one.
- **Solution:** `--retry N` re-runs failures **automatically in the same run**. A
  test that fails then passes is reported as **flaky** (not a build break), so
  real failures stay visible and transient blips don't fail CI.

### 7. File-level retry (dependency-safe)
- **Problem:** Re-running only the single failed test breaks when that test
  depended on earlier tests in its file — their state is gone, so it fails again.
- **Solution:** Retry re-runs the **whole failing file**, preserving the in-file
  sequence, so dependent tests get their prerequisites.

### 8. Single, standard merged report
- **Problem:** Parallel execution produces many `output.xml` fragments; CI needs
  one report.
- **Solution:** All worker outputs (and all retry attempts) fold into one standard
  **`output.xml` + `log.html` + `report.html`** — a drop-in for existing CI and
  reporting tools. (Note: pabot also merges; this is parity. The retry-merge below
  is the differentiator.)

### 9. Correct retry-merge (override, not duplicate)
- **Problem:** Naively merging parallel outputs *plus* retry outputs either fails
  ("different root suites") or **double-counts** retried tests (a test shows up
  once as FAIL and once as PASS).
- **Solution:** ropa does the retry override on the result model itself, keyed
  by test name (workers run with a stable root name), so each test appears
  **exactly once** with its final outcome. Verified: 30-test run with retries
  merges to 30, not 51.

### 10. Crash-safe result accounting
- **Problem:** A worker subprocess can die mid-file (browser crash, OOM kill
  elsewhere); those tests could silently vanish from the report.
- **Solution:** Any test that doesn't appear in a worker's output is recorded as
  **ERROR**, never dropped — the report always accounts for every test.

### 11. Process isolation per file (clean teardown)
- **Problem:** A shared browser server, if killed, orphans Chromium process trees
  that pile up RAM across CI runs.
- **Solution:** Each file is a self-contained subprocess that owns its browser
  lifecycle; on completion nothing is left behind (verified: 0 leaked Chromium
  processes after runs).

### 12. Tag include / exclude
- **Problem:** You often want to run a subset (smoke, a single area).
- **Solution:** `--include` / `--exclude` by tag, same semantics as robot.

### 13. Discovery via Robot Framework's own parser
- **Problem:** A separate discovery mechanism can diverge from what `robot`
  actually runs (different tag filtering, parsing).
- **Solution:** ropa discovers tests with Robot Framework's own
  `TestSuiteBuilder`, so discovery == execution semantics.

### 14. Drop-in CLI / standard reports
- **Problem:** A new tool nobody can adopt is useless.
- **Solution:** Point it at existing suite paths, get standard reports out; no
  changes to test files.

```bash
ropa -p 8 --max-ram 12G --retry 1 tests/
```

---

# Part 2 — pabot vs ropa

| Capability | pabot | ropa |
|---|---|---|
| Parallel execution of suites | ✅ | ✅ |
| Dynamic work distribution to free workers | ✅ (suite queue) | ✅ (file queue) |
| **Concurrency model** | **Fixed `--processes N`, hand-picked** | **Floats to fit a RAM budget** |
| **Memory awareness** | **None — can OOM/thrash** | **Credit budget + live free-RAM floor → never OOM** |
| **Learns per-suite/file RAM** | ❌ | ✅ persisted, self-tuning |
| Runtime-history balancing | partial (manual `--ordering`) | ✅ automatic, heaviest-first |
| Splits a file across workers | ✅ (`--testlevelsplit`) — can break in-file order | ❌ never — file is atomic |
| **Built-in retry of failures** | ❌ manual `--rerunfailed` + `rebot --merge` | ✅ `--retry N`, automatic |
| **Flaky detection** | ❌ | ✅ pass-on-retry → flaky, not failure |
| Retry granularity | individual test | whole file (dependency-safe) |
| Merge into one report | ✅ | ✅ (and correct under retry: override, no dupes) |
| Crash-safe accounting (missing → ERROR) | partial | ✅ |
| Resource locking (shared DB/device/account) | ✅ **PabotLib** | ❌ not yet |
| Ordering files / grouping (`#WAIT`, `{}`) | ✅ | ❌ (file isolation assumed) |
| Hooks / plugin ecosystem | ✅ mature | ❌ minimal |
| Distributed across machines | partial via tooling | ❌ (out of scope — single box) |

**Honest summary.** pabot is mature and has things ropa does not — most notably
**PabotLib resource locking**, ordering files, and a plugin ecosystem. ropa
wins decisively on the one axis it was built for: **running browser tests on a
fixed-RAM machine without OOMing**, plus a better retry story (inline, automatic,
flaky-aware, dependency-safe) and a correct retry-merge. If your constraint is
"one box, limited RAM, lots of Playwright files," ropa is built for exactly
that; if you need cross-test resource locking or a big plugin ecosystem today,
pabot still leads there.

---

# Part 3 — Suggested additional features (not yet built)

Each is framed the same way: problem → proposed feature.

### A. Makespan / auto-concurrency oracle
- **Problem:** You still guess `-p`. Too low wastes the budget; too high just
  queues.
- **Feature:** From learned per-file time **and** RAM, compute and *recommend* the
  concurrency that minimizes wall-clock within the budget, and report the floor:
  *"your run is bounded by `checkout.robot` at 90 s; more than 6 concurrent won't
  help."* Optionally auto-set `-p`.

### B. Test-impact selection
- **Problem:** A one-line change triggers the whole suite in CI.
- **Feature:** Map each file → (resource files, libraries, app surface) it uses;
  on a diff, run only the files whose dependency closure intersects the change.
  Usually the single biggest CI time saver. Clean because files are isolated.

### C. Live progress / dashboard
- **Problem:** Mid-run you can't see what's running, what's queued (waiting on
  RAM), or the ETA.
- **Feature:** A live view — running files, queued files with their RAM cost,
  current memory headroom, ETA from history. Turns "is it stuck?" into a glance.

### D. Per-file RAM & timing in the report
- **Problem:** You can't see *why* concurrency was what it was.
- **Feature:** Surface each file's learned RAM and duration in the report, and a
  summary: peak RAM used vs budget, number of waves, files that throttled
  concurrency. Makes the scheduler's decisions transparent.

### E. Resource locking (PabotLib-equivalent)
- **Problem:** Some files share a scarce external resource (one test account, one
  device, a limited license) and must not run at the same time — even though they
  fit RAM.
- **Feature:** Declare named resources with capacity; the scheduler treats them as
  *additional* credits alongside RAM (a file needing `account:1` waits until one
  is free). Closes the main gap vs pabot.

### F. Browser / long-run recycling
- **Problem:** Chromium leaks and doesn't return memory to the OS; a 30-minute run
  can creep upward.
- **Feature:** Periodically recycle browser processes / cap a worker's lifetime so
  long runs stay within budget.

### G. CI niceties
- **Problem:** CI wants machine-readable output and predictable exit codes.
- **Feature:** JUnit XML export, stable exit codes (failures vs flaky vs error),
  and a one-line machine-readable summary.

### H. Optional graceful degradation under pressure
- **Problem:** If the box unexpectedly loses RAM mid-run (another job spikes),
  you'd want to back off rather than risk swap.
- **Feature:** When live free RAM dips toward the floor, *stop admitting* (already
  done) and optionally let the heaviest running file finish before others start —
  adaptive back-off, like congestion control.
