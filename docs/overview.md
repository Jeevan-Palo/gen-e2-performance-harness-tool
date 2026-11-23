# Performance Harness: Overview

A repeatable way to go from client documents to a tested k6 load script and a recorded run. Copilot drafts the work in VS Code. Python scripts check it against fixed rules.

## How we start

1. Install the Python dependencies (`python -m pip install -r requirements.txt`) and k6 (`brew install k6`).
2. Open the repo in VS Code with GitHub Copilot Chat in Agent mode.
3. Type `/start-project` and give the client and application name.

## Steps

| Step | Command | What it does | Output | Where |
|---|---|---|---|---|
| 1. Start project | `/start-project` | Creates the client and app folder with a `sources/` folder | Project folder | [.github/prompts/start-project.prompt.md](../.github/prompts/start-project.prompt.md) |
| 2. Requirements intake | Put client files in `sources/`, then ask Copilot to run intake | Reads BRD, emails and notes. Extracts them without inventing values. Lists what is missing | `brd.yaml`, missing list | [.github/skills/requirements-intake/SKILL.md](../.github/skills/requirements-intake/SKILL.md), [tools/brd.py](../tools/brd.py) (`check`) |
| 3. BRD and gap questions | Answer Copilot's questions (max 5 at a time) | Fills gaps from your answers. Every value is traced to a source | `brd.md` (client-readable), `open-items.md` | [.github/skills/brd-builder/SKILL.md](../.github/skills/brd-builder/SKILL.md), [tools/brd.py](../tools/brd.py) (`render`) |
| 4-5. API catalogue | `/build-catalogue` | Imports Postman, OpenAPI or HAR files. If none exist, does read-only browser discovery. Never sends load | `api-catalogue.yaml` | [.github/prompts/build-catalogue.prompt.md](../.github/prompts/build-catalogue.prompt.md), [tools/catalogue.py](../tools/catalogue.py) |
| 6. Target check | `python tools/targetcheck.py <project>` | Binds results to the active base URL, blocks redirects outside its exact origin, URL-encodes required query parameters, and compares exact response status and fields; does not send writes or log in | `target-check.json` | [tools/targetcheck.py](../tools/targetcheck.py) |
| 7. k6 script | `/build-script` | Builds the needed baseline, stepped-ramp, stress, spike and endurance scenarios from the BRD; each profile selects catalogue flows. Checks it against the BRD and catalogue; does not run it | `k6/script.js`, `k6/requirement-map.yaml` | [.github/prompts/build-script.prompt.md](../.github/prompts/build-script.prompt.md), [tools/k6check.py](../tools/k6check.py) |
| 8. Run | `/run-test` | Smoke first. Baseline repetitions require visible monitoring and a consistency check; stepped ramp requires signed-off baseline and enforces a 2x step limit. Stress, spike and endurance have profile-specific guards | `runs/<run-id>/run.json`, `summary.json`, `k6-output.txt` | [.github/prompts/run-test.prompt.md](../.github/prompts/run-test.prompt.md), [tools/runk6.py](../tools/runk6.py), [tools/baseline.py](../tools/baseline.py) |
| 9. Monitoring | Configured in `environments.yaml` | Collects Docker CPU and memory data during local runs; other collectors are not built | `runs/<run-id>/monitoring.json` | [tools/monitor.py](../tools/monitor.py) |
| 10. Report | `/build-report` or automatic after a run | Reports p50/p90/p95/p99, TPS, errors, CPU/memory, DB metrics when collected, strict RAG, saturation observations, run comparisons, coverage and exit criteria. Findings are evidence-only unless human-approved text is in the BRD | `runs/<run-id>/report.html` | [tools/report.py](../tools/report.py) |
| 11. Client pack | `/build-pack` | Builds a local pack and ZIP with coverage matrix and exit-criteria status; `--run` accepts only a passed load run | `client-pack/` | [tools/clientpack.py](../tools/clientpack.py) |

The complete workflow can be started or resumed with `/run-end-to-end`. Check the project's next stage with `python tools/status.py <project>`. Azure, Dynatrace and client APM collectors remain deferred until a project identifies its provider and supplies access details.

## Repo layout

- `.github/`: Copilot instructions, prompts (slash commands) and skills (step guides).
- `templates/`: BRD and API catalogue templates. Never edited per project.
- `tools/`: Python helpers (`brd.py`, `catalogue.py`, `k6check.py`, `runk6.py`). Always used for checks and runs.
- `projects/<client>/<app>/`: one folder per client application, holding its sources and outputs.

## Rules that always apply

- No invented values. Anything not in a source or in your answer stays empty and is asked about.
- No real personal or payment data, and no passwords or tokens in any file.
- Discovery is read-only. No load is sent until the test is approved.
- Stated, assumed and open items are kept separate.

## Project status

Project contents and run history change over time. Do not rely on a status snapshot in this overview; run `python tools/status.py projects/<client>/<app>` for the current stage and next action.
