---
name: end-to-end
description: Run the whole performance-testing flow for a project by looping on tools/next.py (which builds on tools/status.py). Do the next unfinished stage with the right skill or tool, stop only at the human decisions listed below, and resume from the files after any interruption. Use when the user says to start or continue a project end to end.
---

# End to end

`python tools/status.py projects/<client>/<app>` works out from the files which stages are done and what comes next. It is the source of truth; never mark a stage done by hand, and never skip one. `STATE.md` is only a short note (8 lines).

## Loop
1. Run `python tools/next.py projects/<client>/<app>`. It builds on `status.py` and prints either `PROCEED` (do the stated action), `STOP` (a human decides first; see the gate id) or `ALL STAGES DONE`. Exit code 0 = done, 1 = proceed, 2 = stop. Use `--json` for the fields `stage`, `actor` (tool, copilot or human), `skill`, `command`, `gate`, `ask`.
2. PROCEED: do that stage as in the table below, with the skill or tool it names. Then run `next.py` again and report in one or two sentences what changed.
3. STOP: ask the user exactly the gate's `ask`, in one message, and wait. Never act on a gate yourself; only the user's answer clears it (the answer is recorded in the project files, then `next.py` moves on).
4. Repeat until `ALL STAGES DONE`. Resuming after a break is the same: just run `next.py`.

## Stages
| Stage | What to do | Skill or tool |
|---|---|---|
| 1 BRD | Read the sources, fill `brd.yaml`, ask for missing parameters, render the BRD, then build the client Word file with `python tools/brdexport.py <project>` (status shows it missing or stale; rebuild after any BRD or environment change) | `requirements-intake`, `brd-builder` |
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
`load_steps: [2, 4, 5]`, `ramp_up: 30s`, `steady: 3m`, `ramp_down: 30s`, `discovery_actions: [<write actions of this application's flows, e.g. login, submit order>]`, `pack_if_targets_missed: true`. Take the actions from this project's BRD transactions, never from another project.
Steps must respect `max_vus` (first step at most 5, then at most 2x); `envconf.py check` enforces this.

## Gate ids (returned by `tools/next.py`; these are the only gates the tool raises)
- `sources`: `sources/` is empty. Ask the user to add the client's files.
- `business_facts`: must-haves still missing after intake. One message: questions, advised values, run plan.
- `environment`: `environments.yaml` missing or failing `envconf.py check`.
- `authorisation`: the environment is `not_confirmed`. Only the user decides; record their statement and date in `authorisation_note`.
- `credentials`: the catalogue needs a login and the `credentials_env_vars` are not exported. The user runs the target check in their own terminal.
- `run_plan`: no approved run plan at the load stage.
- `failed_run`: the latest run was aborted, errored, or the smoke run did not pass. Never retry on your own.
- `targets_missed`: a load run missed targets and the plan does not allow packing missed targets.

Stop points that need judgement and are not detected by the tool (a write action outside the plan during discovery, an unexplained target-check difference, an app with no backend API) are listed below; raise them yourself.

## Stop and ask the user only for
- Stage 1: the business facts and the "accept advised values" reply (see `requirements-intake`), in one message. Never ask a field twice.
- Stage 1 Word file: never a stop. Build it, tell the user its path and the Stated / Advised / Assumed / Not evidenced / Open counts, say it is for the client to review and sign, then carry on. Do not wait for a signed return, and never fill its sign-off or send it.
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
