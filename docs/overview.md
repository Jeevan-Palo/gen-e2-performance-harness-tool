# Performance Harness: Overview

A repeatable way to go from client documents to a tested k6 load script and a recorded run. Copilot drafts the work in VS Code. Python scripts check it against fixed rules.

## How we start

1. Install Python package `pyyaml` (`pip install pyyaml`) and k6 (`brew install k6`).
2. Open the repo in VS Code with GitHub Copilot Chat in Agent mode.
3. Type `/start-project` and give the client and application name.

## Steps

| Step | Command | What it does | Output | Where |
|---|---|---|---|---|
| 1. Start project | `/start-project` | Creates the client and app folder with a `sources/` folder | Project folder | [.github/prompts/start-project.prompt.md](../.github/prompts/start-project.prompt.md) |
| 2. Requirements intake | Put client files in `sources/`, then ask Copilot to run intake | Reads BRD, emails and notes. Extracts them without inventing values. Lists what is missing | `brd.yaml`, missing list | [.github/skills/requirements-intake/SKILL.md](../.github/skills/requirements-intake/SKILL.md), [tools/brd.py](../tools/brd.py) (`check`) |
| 3. BRD and gap questions | Answer Copilot's questions (max 5 at a time) | Fills gaps from your answers. Every value is traced to a source | `brd.md` (client-readable), `open-items.md` | [.github/skills/brd-builder/SKILL.md](../.github/skills/brd-builder/SKILL.md), [tools/brd.py](../tools/brd.py) (`render`) |
| 4-5. API catalogue | `/build-catalogue` | Imports Postman, OpenAPI or HAR files. If none exist, does read-only browser discovery. Never sends load | `api-catalogue.yaml` | [.github/prompts/build-catalogue.prompt.md](../.github/prompts/build-catalogue.prompt.md), [tools/catalogue.py](../tools/catalogue.py) |
| 7. k6 script | `/build-script` | Writes the load script with thresholds and abort rules. Checks it against the BRD and catalogue. Does not run it | `k6/script.js`, `k6/requirement-map.yaml` | [.github/prompts/build-script.prompt.md](../.github/prompts/build-script.prompt.md), [tools/k6check.py](../tools/k6check.py) |
| 8. Run | `/run-test` | Smoke run (1 user) first, then load. Guards: first load run max 5 users, each step at most double the last passed run, 20-minute cap | `runs/<run-id>/run.json`, `summary.json`, `k6-output.txt` | [.github/prompts/run-test.prompt.md](../.github/prompts/run-test.prompt.md), [tools/runk6.py](../tools/runk6.py) |

Monitoring, the final report and the client pack (Step 9 onwards) are not built yet.

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

## Current example: ToolShop

Project: `projects/ToolShop/practicesoftwaretesting/`. It is a practice run on a demo shop, not a client engagement.

- Steps 1–5 and 7 are complete. All three checks pass and no must-have parameters are missing.
- Open items remain (9 in `brd.yaml`, see `open-items.md`). The main ones are API parity with the local copy, rate limits, and test accounts.
- Load has not been run yet. A smoke run is recorded in `k6/smoke-summary.json`, but no `runs/` record exists for it. This needs to be checked before it is shown.

Key files:

- [brd.yaml](../projects/ToolShop/practicesoftwaretesting/brd.yaml): the single source of truth for requirements
- [STATE.md](../projects/ToolShop/practicesoftwaretesting/STATE.md): current stage and blockers
- [k6/script.js](../projects/ToolShop/practicesoftwaretesting/k6/script.js): the load script (not yet run)
