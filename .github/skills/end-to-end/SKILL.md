---
name: end-to-end
description: Run the whole performance-testing flow for a project by looping on tools/status.py. Do the next unfinished stage with the right skill or tool, stop only at the human decisions listed below, and resume from the files after any interruption. Use when the user says to start or continue a project end to end.
---

# End to end

`python tools/status.py projects/<client>/<app>` works out from the files which stages are done and what comes next. It is the source of truth; never mark a stage done by hand, and never skip one. `STATE.md` is only a short note (8 lines).

## Loop
1. Run `python tools/status.py projects/<client>/<app>`. Read the NEXT line.
2. Do that stage as in the table. After it, run status again and report in one or two sentences what changed.
3. Repeat until it prints `ALL STAGES DONE`, or until you reach a human decision (below). Resuming after a break is the same: just run status.

## Stages
| Stage | What to do | Skill or tool |
|---|---|---|
| 1 BRD | Read the sources, fill `brd.yaml`, ask for missing parameters, render the BRD | `requirements-intake`, `brd-builder` |
| 2 Environment | Help the user fill `environments.yaml` (URL, owner, limits, monitoring); run `envconf.py check` | the user decides the values |
| 3 Catalogue | Build `api-catalogue.yaml` from supplied files, else discover in the browser or from a HAR file | `api-source-selector`, then `api-catalogue-from-postman`, `api-catalogue-from-sources` or `api-discovery-browser` |
| 4 Target check | `python tools/targetcheck.py <project>` (read calls only; if the catalogue needs a login, the user runs it in their own terminal with the `credentials_env_vars` exported, and it sends one login POST) | tool |
| 5 Script | Generate the k6 script and pass `k6check.py` | `k6-script-builder` |
| 6 Smoke | `tools/runk6.py <project> --profile smoke` | `k6-run` |
| 7 Load | Step up through `tools/runk6.py`, one run at a time | `k6-run`, `monitoring-evidence` |
| 8 Report | Built automatically after each run; if missing, `tools/report.py` | `report-builder` |
| 9 Client pack | `tools/clientpack.py <project>` | `client-pack` |

## Run plan (ask once, at the start)
Ask in the same message as the stage 1 questions, so the flow then runs without stopping. Write the answer into the active environment's `run_plan` in `environments.yaml`, with the user's own statement and date in `approved_note`. Ready-to-accept example:
`load_steps: [2, 4, 5]`, `ramp_up: 30s`, `steady: 3m`, `ramp_down: 30s`, `discovery_actions: [login, add to cart, checkout]`, `pack_if_targets_missed: true`.
Steps must respect `max_vus` (first step at most 5, then at most 2x); `envconf.py check` enforces this.

## Stop and ask the user only for
- Stage 1: the business facts and the "accept advised values" reply (see `requirements-intake`), in one message. Never ask a field twice.
- Stage 2: the environment URL and owner if not given, and the `authorisation` value. Only the user sets authorisation; record their statement and date in `authorisation_note`.
- Stage 3: a write action during discovery that is not in `run_plan.discovery_actions`. If the environment is `not_confirmed`, do not browse it.
- Stage 4: a target-check difference you cannot explain from the catalogue (for example a page that needs a login is not a difference: set its `auth` and re-run the check). Do not change the catalogue to hide a real difference.
- Stage 5: an app with no backend APIs needs the k6 browser module; this is allowed when the plan or the user approves it (see `k6-script-builder`).
- Stage 6/7: a smoke run that fails, any aborted or errored run, or no approved run plan (then ask for users and durations). Never repeat an aborted or failed run on your own. With a plan, run its steps in order and report each outcome (p95, p99, CPU, memory) in one or two lines.
- Stage 9: after building the pack, tell the user to read the cover page before sharing it. Never share, send or upload it.

## Never
- Never change an `authorisation` value, use `--force-step`, or type a URL for a run.
- Never edit run files, reports, monitoring data or the client pack, and never add conclusions by hand.
- Never claim a stage is done without status showing it.
