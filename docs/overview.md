# Performance Harness: Overview

A repeatable way to go from client documents to a tested k6 load run and a client pack. Copilot drafts the work in VS Code. Python tools check it, run it and report it against fixed rules. Setup, ground rules and troubleshooting are in the [README](../README.md).

## How it works

- **Instructions** ([.github/copilot-instructions.md](../.github/copilot-instructions.md)): the rules Copilot always follows.
- **Prompts** ([.github/prompts/](../.github/prompts)): the slash commands. They are thin; the detail lives in the skills.
- **Skills** ([.github/skills/](../.github/skills)): one guide per stage. [end-to-end](../.github/skills/end-to-end/SKILL.md) loops on `tools/status.py` and calls the others.
- **Tools** ([tools/](../tools)): deterministic Python. `status.py` is the source of truth for which stage is done and what is next; `doctor.py` checks the machine.
- **Projects** (`projects/<client>/<app>/`): one folder per client application with its sources, BRD, environments, catalogue, script, runs and pack.

## Stages

| # | Stage | Prompt or skill | Tool |
|---|---|---|---|
| 1 | BRD (intake, gap questions, Word file for the client) | `requirements-intake`, `brd-builder` | `brd.py`, `brdexport.py` |
| 2 | Environment and authorisation | you fill `environments.yaml` | `envconf.py` |
| 3 | API catalogue | `/build-catalogue`, `api-source-selector` and the catalogue skills | `catalogue.py` |
| 4 | Target check (read-only) | `end-to-end` | `targetcheck.py` |
| 5 | k6 script | `/build-script` | `k6check.py` |
| 6 | Smoke run | `/run-test` | `runk6.py` |
| 7 | Load runs and monitoring | `/run-test`, `monitoring-evidence` | `runk6.py`, `monitor.py` |
| 8 | Report | `/build-report` | `report.py` |
| 9 | Client pack | `/build-pack` | `clientpack.py` |

Start with `/check-setup` once, then `/run-end-to-end` (or `/start-project` for a new project).

## Rules that always apply

- No invented values. Anything not in a source or in your answer stays empty and is asked about.
- No real personal or payment data, and no passwords or tokens in any file.
- Discovery is read-only. No load is sent until the test is approved and the environment is authorised.
- Stated, assumed and open items are kept separate.
- Nothing is sent to the client or anyone else by the harness.

## Example projects

`projects/_example/` is the sanitised sample for a first dry run. Other folders under `projects/` are real practice or client runs; their state is in each project's `STATE.md`, and `python tools/status.py <project>` shows the current stage.
