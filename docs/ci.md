# ropa in CI/CD — used exactly like pabot

ropa is a drop-in for pabot in a pipeline: same place in `requirements.txt`, same
kind of command, same suite paths, same standard reports as artifacts. The one
difference — and the reason to use it in CI — is the **`--max-ram` budget**: CI
runners have fixed RAM, and ropa admits files only while they fit, so a
browser-heavy parallel run **can't OOM the runner**.

**No xvfb / no display needed — exactly like pabot.** ropa never launches a
browser itself; it only runs `robot`. Headless is decided by your suites
(`New Browser ... headless=True`, or your config), so Playwright Chromium runs
headless natively in CI with no `xvfb-run` and no `DISPLAY`. (Verified on a real
Browser/Playwright suite.)

## 1. Install (same slot as `robotframework-pabot`)

In `requirements.txt`, replace the pabot line with ropa:

```diff
  robotframework==7.2.2
  robotframework-browser==20.0.0
- robotframework-pabot==5.2.2
+ ropa @ git+https://github.com/Surendrraa/ropa.git@v0.1.1
```

Then the usual:

```bash
pip install -r requirements.txt
rfbrowser init            # Playwright browsers (same as for pabot + Browser)
```

## 2. Command — one-line swap

```diff
- pabot --processes 4              --outputdir reports/all tests
+ ropa  -p 4       --max-ram 7G    --outputdir reports/all tests
```

Set **`--max-ram` to the runner's RAM minus ~1 GB headroom**:

| Runner RAM | `--max-ram` |
|---|---|
| 4 GB (Bitbucket `size: 1x`) | `3G` |
| 8 GB (Bitbucket `size: 2x`) | `7G` |
| 16 GB | `14G` |

Add `--retry 1` to auto-retry flaky files (no separate rerun step, unlike pabot).

## 3. Exit code

ropa exits **non-zero when tests fail** (Robot Framework convention: the number
of failed tests), so the pipeline step fails correctly. A test that fails then
passes under `--retry` is reported **flaky** and does **not** fail the build.

## 4. Bitbucket Pipelines (mirrors a pabot setup)

```yaml
image: python:3.11-bookworm
options:
  size: 2x          # 8 GB memory

pipelines:
  default:
    - step:
        name: Robot tests (ropa)
        size: 2x
        script:
          - python -m venv .venv && . .venv/bin/activate
          - pip install -r requirements.txt
          - rfbrowser init
          - ropa -p 4 --max-ram 7G --retry 1 --outputdir reports/all tests
        artifacts:
          - reports/**
```

If you keep a wrapper script (like `ci/run-pabot-xvfb.sh`), the body becomes:

```bash
processes="${ROPA_PROCESSES:-4}"
ropa -p "${processes}" --max-ram "${ROPA_MAX_RAM:-7G}" \
     --retry "${ROPA_RETRY:-1}" --outputdir "reports/${suite_name}" "$@"
```

## 5. GitHub Actions

```yaml
jobs:
  robot:
    runs-on: ubuntu-latest        # 7 GB RAM
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt && rfbrowser init
      - run: ropa -p 4 --max-ram 6G --retry 1 --outputdir reports/all tests
      - uses: actions/upload-artifact@v4
        if: always()
        with: { name: robot-report, path: reports/** }
```

## Notes

- **Headless** browsers work in CI with no xvfb (Playwright Chromium is headless
  natively) — same as your current pabot setup.
- ropa writes `.ropa/` (learned per-file RAM + timing) in the working dir; in CI
  it's recreated each run unless you cache it. Caching `.ropa/` across runs lets
  the scheduler pack better over time, but it is optional.
- Everything else (suite paths, `-i/-e` tags, the merged `output.xml` /
  `log.html` / `report.html`) is the same as pabot.
