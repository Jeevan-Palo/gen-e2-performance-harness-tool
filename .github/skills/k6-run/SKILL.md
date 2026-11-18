---
name: k6-run
description: Run the project's k6 script safely (smoke first, then load at the user count the user chooses), record the run with exact UTC start and end times, and report the outcome. Use for Step 8 of the performance flow.
---

# k6 run (Step 8)

Always run through `tools/runk6.py`. Never call `k6 run` directly. The wrapper checks the script, enforces the guards, records the run and saves the results in `projects/<client>/<app>/runs/<run-id>/`.

## Preflight
1. Run `k6 version`. If k6 is not installed, tell the user, show the install command for their OS (macOS: `brew install k6`), run it only through the terminal so the user can approve it, and re-check. Install nothing else without asking.
2. `python tools/envconf.py check`, `python tools/brd.py check`, `python tools/catalogue.py check` and `python tools/k6check.py` for the project must pass. Tell the user which environment is active (`python tools/envconf.py show <project>`) before running. If not, stop and tell the user.

## Procedure
1. Ask the user how many users and what durations they want if they did not say. Use exactly what they choose; do not raise it. Default shape for a small run: 30s ramp-up, 3m steady, 30s ramp-down.
2. Smoke first (1 user, 1 pass): `python tools/runk6.py projects/<client>/<app> --profile smoke`
3. If smoke outcome is `passed`, run the load test the user chose:
   `python tools/runk6.py projects/<client>/<app> --profile load --vus <N> --ramp-up 30s --steady 3m --ramp-down 30s`
4. Read the OUTCOME line and `run.json`, and tell the user in plain words:
   - `passed`: all thresholds met. Give the run id, the UTC window, and the p95 and p99 per transaction from `summary.json`.
   - `thresholds_failed`: the run finished but a requirement was missed. List which thresholds.
   - `aborted_by_threshold`: a safety rule stopped the run early (error rate, slow responses, or 429/503/CDN block). Say which, and do NOT re-run automatically.
   - `error`: the script or k6 failed. Show the last lines of `k6-output.txt`.
5. Ask the user before any further run. A bigger run only happens when the user asks for it.
6. Update `STATE.md` (stage "8. Run", latest run id and outcome).

## Rules
- Never use `--force-step` unless the user explicitly approves that exact jump in this chat.
- The target and limits come from `environments.yaml`. Use `--env NAME` only when the user names an environment. Never type a URL, and never change the `authorisation` value yourself.
- Never retry an aborted run on your own, and never re-run to get a better number.
- Never edit `summary.json`, `run.json` or `k6-output.txt`.
- A run on an environment whose authorisation is `not_confirmed` is refused. The first load run is limited to 5 users, later runs to at most 2x the highest passed run on that environment, and `max_vus` and `max_run_minutes` of the environment are hard caps; the tool enforces all of this.
- Do not collect monitoring data or write the report in this step.
