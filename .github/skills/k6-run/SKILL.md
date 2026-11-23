---
name: k6-run
description: Run the project's k6 script safely (smoke first, then load at the user count the user chooses), record the run with exact UTC start and end times, and report the outcome. Use for Step 8 of the performance flow.
---

# k6 run (Step 8)

Always run through `tools/runk6.py`. Never call `k6 run` directly. The wrapper checks the script, enforces the guards, records the run and saves the results in `projects/<client>/<app>/runs/<run-id>/`.

## Preflight
0. For a Baseline profile, the wrapper requires a successful visible-monitoring preflight. For other profiles, run the preflight when the source is `docker_stats`; report if unavailable.
1. Run `k6 version`. If k6 is not installed, tell the user, show the install command for their OS (macOS: `brew install k6`), run it only through the terminal so the user can approve it, and re-check. Install nothing else without asking.
2. `python tools/envconf.py check`, `python tools/brd.py check`, `python tools/catalogue.py check` and `python tools/k6check.py` for the project must pass. Tell the user which environment is active (`python tools/envconf.py show <project>`) before running. If not, stop and tell the user.

## Procedure
1. Ask the user how many users and what durations they want if they did not say. Use exactly what they choose; do not raise it. Default shape for a small run: 30s ramp-up, 3m steady, 30s ramp-down.
2. Smoke first (1 user, one pass over active load-safe flows): `python tools/runk6.py projects/<client>/<app> --profile smoke`
3. If Baseline is needed, run it the BRD-specified number of times after smoke, then check it with `python tools/baseline.py check <project>`. Consistency is the coefficient of variation across common measured metrics and must be strictly below the BRD limit. Only after reviewing the recorded metrics may a human sign off with `python tools/baseline.py sign-off <project> --by "<approver>" --date YYYY-MM-DD`.
4. For a stepped ramp, choose a user count listed in the BRD and run `python tools/runk6.py projects/<client>/<app> --profile load --vus <N>`. A passed smoke and signed-off baseline (when required) are gates. The 2x rule applies to ramp steps only.
5. Stress requires explicit `--vus` plus agreed abort, rollback and on-call information. Spike and Endurance use their BRD-defined values; Spike/Endurance are not subject to the 2x ramp rule. Endurance also requires the active environment's reserved window/data volume.
6. Read the OUTCOME line and `run.json`, and tell the user in plain words:
   - `passed`: all thresholds met. Give the run id, the UTC window, and the p95 and p99 per transaction from `summary.json`.
   - `thresholds_failed`: the run finished but a requirement was missed. List which thresholds.
   - `aborted_by_threshold`: a safety rule stopped the run early (error rate, slow responses, or 429/503/CDN block). Say which, and do NOT re-run automatically.
   - `error`: the script or k6 failed. Show the last lines of `k6-output.txt`.
7. Profile runs save their BRD parameters and selected flow IDs in `run.json`; `runk6.py` also builds `report.html` after every run. Give the user the report path.
8. Ask the user before any further run. A bigger run only happens when the user asks for it.
9. Update `STATE.md` (stage "8. Run", latest run id and outcome).

## Rules
- Never use `--force-step` unless the user explicitly approves that exact jump in this chat.
- The target and limits come from `environments.yaml`. Use `--env NAME` only when the user names an environment. Never type a URL, and never change the `authorisation` value yourself.
- Never retry an aborted run on your own, and never re-run to get a better number.
- Never edit `summary.json`, `run.json` or `k6-output.txt`.
- A run on an environment whose authorisation is `not_confirmed` is refused. The first ramp step is limited to 5 users, each subsequent ramp step to at most 2x the last passed step, and `max_vus` and `max_run_minutes` of the environment are hard caps; the tool enforces these limits.
- Do not collect monitoring data or write the report in this step.
