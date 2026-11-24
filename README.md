# perf-harness

Client documents in, a tested k6 load run and a client pack out. Copilot (VS Code, Agent mode) does the drafting; the Python tools in `tools/` do every check, run and report. Overview: [docs/overview.md](docs/overview.md).

## Prerequisites
| Needed | For | Install |
|---|---|---|
| VS Code with GitHub Copilot and Copilot Chat (recent version, Agent mode) | everything | https://code.visualstudio.com |
| Python 3.9+ | everything | https://www.python.org (macOS: `brew install python`) |
| k6 | script check and runs (stages 5-7) | https://grafana.com/docs/k6/latest/set-up/install-k6/ (macOS: `brew install k6`) |
| pandoc | the Word file the client signs (stage 1) | https://pandoc.org/installing.html (macOS: `brew install pandoc`) |
| Docker | only when monitoring source is `docker_stats` (stage 7) | Docker Desktop or Rancher Desktop |

## Set up (once, about 5 minutes)
1. Clone the whole repository (do not copy single folders; `.github/` holds the prompts and skills).
2. Run `./setup.sh` (macOS/Linux) or `powershell -File setup.ps1` (Windows). It creates `.venv`, installs `requirements.txt` and runs the doctor.
   Do not use a bare `pip install`: on Homebrew and many Linux Pythons it is refused ("externally-managed-environment"). Always use the `.venv`.
3. Open the folder in VS Code, accept the recommended extensions, and pick the interpreter `.venv` (Command Palette: *Python: Select Interpreter*). New terminals then use it, so `python` works.
4. Check everything: `python tools/doctor.py`, or `/check-setup` in Copilot Chat. A `FAIL` must be fixed; a `WARN` only affects the stage it names.
5. Check the harness itself: `python tools/lint.py` and `python -m unittest discover -s tests` (both must pass).

## Use it
Open Copilot Chat, switch to **Agent** mode, and type:
- `/run-end-to-end` for a new or existing project. It runs `python tools/status.py <project>`, does the next unfinished stage and stops only at human decisions (missing business facts, environment and authorisation, write actions, a failed or aborted run, sharing the pack).
- `/start-project` to create a new project and go straight through to the client pack.
- Or one stage at a time: `/build-catalogue`, `/build-script`, `/run-test`, `/build-report`, `/build-pack`.
- To see where a project stands, or resume after a break: `python tools/status.py projects/<client>/<app>`.

Put the client's files in `projects/<client>/<app>/sources/` before intake.

## The nine stages (as printed by `tools/status.py`)
| # | Stage | Tool that does the work | Output |
|---|---|---|---|
| 1 | BRD | `brd.py` (`check`, `questions`, `advise`, `render`), `brdexport.py` | `brd.yaml`, `brd.md`, Word file for client sign-off |
| 2 | Environment | `envconf.py` (`check`, `show`, `use`) | `environments.yaml` (you set `authorisation`) |
| 3 | API catalogue | `catalogue.py` (`import-postman`, `import-openapi`, `import-har`, `check`) | `api-catalogue.yaml` |
| 4 | Target check | `targetcheck.py` (read calls only) | `target-check.json` |
| 5 | k6 script | `k6check.py` | `k6/script.js`, `k6/requirement-map.yaml` |
| 6 | Smoke run | `runk6.py --profile smoke` | `runs/<run-id>/` |
| 7 | Load runs + monitoring | `runk6.py`, `monitor.py` | `runs/<run-id>/` incl. `monitoring.json` |
| 8 | Report | `report.py` (automatic after each run) | `runs/<run-id>/report.html` |
| 9 | Client pack | `clientpack.py` | `client-pack/` and a `.zip` |

Environments: `environments.yaml` has one block per environment (URL, owner, authorisation, limits, monitoring, test windows, run plan). Switch with `python tools/envconf.py use <project_dir> <name>`. Runs are refused while `authorisation` is `not_confirmed`.
Monitoring: for a local Docker app set `monitoring: {source: docker_stats, containers: [<names from docker ps>], interval_seconds: 5}`. Azure, Dynatrace and client APM collectors are not built.
Report and pack never send anything; sharing is always your decision.

## Ground rules for everyone who uses this repo
1. **Only test systems you are authorised to test.** Record the owner's authorisation in `environments.yaml`. Never set `authorisation` just to get a run through, and never use `--force-step`.
2. **No secrets in any file.** Credentials are environment variables; files hold only their names. Redact tokens, cookies and personal data from sources.
3. **Never invent a value.** Unknown means empty plus an open item; the tools and Copilot must ask.
4. **Runs only through `tools/runk6.py`**, reports only through `tools/report.py`, the pack only through `tools/clientpack.py`. Never edit files under `runs/` or `client-pack/` by hand.
5. **Keep real client data out of shared copies.** `projects/<client>/` holds client documents and results; share or push it only where the client allows. Keep only `projects/_example/` in a public copy.
6. **Start small.** Smoke first, first load step at most 5 users, then at most double the last passed step.
7. **After changing `tools/`, `.github/` or `templates/`** run `python tools/lint.py` and `python -m unittest discover -s tests`. Never weaken a check or a test to make it pass.
8. **Do not add extra documents** (status logs, handoff notes). Project state lives in `brd.yaml`, `environments.yaml`, `open-items.md`, `api-catalogue.yaml` and `STATE.md`.

## Troubleshooting
| Symptom | Cause and fix |
|---|---|
| `ModuleNotFoundError: No module named 'yaml'` | Not using the venv. Run `./setup.sh`, then use `.venv/bin/python` or open a new VS Code terminal after selecting the interpreter. |
| `externally-managed-environment` on `pip install` | Do not install globally. Use `./setup.sh` (it uses `.venv`). |
| `python: command not found` | Use `python3`, or `.venv/bin/python` (Windows: `.venv\Scripts\python`). |
| `/run-end-to-end` and other slash commands not listed | Use a recent VS Code and Copilot Chat, Agent mode, and keep `.vscode/settings.json` (`chat.promptFiles`, `chat.useAgentSkills`). Open the repo root as the workspace folder. |
| Skills not used | Same as above; also confirm `.github/skills/*/SKILL.md` exists (the doctor counts them). |
| `k6 not found` | Install k6 (see Prerequisites) or set `K6_BIN` to its path. |
| `pandoc is not installed` | Install pandoc. Only the client Word file needs it; status shows stage 1 as not complete until it is built. |
| Run refused: authorisation | The active environment has `authorisation: not_confirmed`. The owner's authorisation must be stated by you in chat; Copilot will not set it. |
| Run refused: users above limit | `max_vus` in `environments.yaml`, or the 5-user first step / 2x rule. Choose an allowed step. |
| `docker stats` shows no data | Wrong container names (`docker ps`) or Docker is not running. Check with `python tools/monitor.py check <project>`. |
| Lint or tests fail on a fresh clone | Run them with the `.venv` Python. If they still fail, open an issue with the full output. |
