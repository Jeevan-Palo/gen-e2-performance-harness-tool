---
name: end-to-end
description: Run the whole performance-testing flow for a project by looping on tools/status.py. Do the next unfinished stage with the right skill or tool, stop at every human decision, and resume from the files after any interruption. Use when the user says to start or continue a project end to end.
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
| 3 Catalogue | Build `api-catalogue.yaml` from supplied files, else discover in the browser or from a HAR file | `api-catalogue-from-sources`, `api-discovery-browser` |
| 4 Target check | `python tools/targetcheck.py <project>` (read calls only) | tool |
| 5 Script | Generate the k6 script and pass `k6check.py` | `k6-script-builder` |
| 6 Smoke | `tools/runk6.py <project> --profile smoke` | `k6-run` |
| 7 Load | Step up through `tools/runk6.py`, one run at a time | `k6-run`, `monitoring-evidence` |
| 8 Report | Built automatically after each run; if missing, `tools/report.py` | `report-builder` |
| 9 Client pack | `tools/clientpack.py <project>` | `client-pack` |

## Always stop and ask the user
- Stage 1: any missing or conflicting requirement value. Ask in groups of at most 5, never guess.
- Stage 2: the environment URL, owner, limits and the `authorisation` value. Only the user sets authorisation; record their statement and the date in `authorisation_note`.
- Stage 3: any write action during discovery needs the user's approval for that exact action. If the environment is blocked (`not_confirmed`), do not browse it.
- Stage 4: if the target check shows differences, show them. Do not change the catalogue to fit without asking.
- Stage 7: before every load run, tell the user the next allowed step and ask how many users and which durations. Use exactly what they choose. After each run, report the outcome, p95 and p99, CPU and memory, and ask whether to step up. Never repeat an aborted or failed run on your own.
- Stage 9: after building the pack, tell the user to read the cover page before sharing it. Never share, send or upload it.

## Never
- Never change an `authorisation` value, use `--force-step`, or type a URL for a run.
- Never edit run files, reports, monitoring data or the client pack, and never add conclusions by hand.
- Never claim a stage is done without status showing it.
