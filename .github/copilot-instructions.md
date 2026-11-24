# Performance Harness: Copilot Instructions

You help a QA lead run client performance testing end to end.
Flow: collect requirements -> BRD -> fill gaps -> API catalogue -> k6 script -> run -> monitor -> report -> client pack.
Stages (the numbers `tools/status.py` prints; use only these): 1 BRD, 2 Environment, 3 API catalogue, 4 Target check, 5 k6 script, 6 Smoke run, 7 Load runs (with monitoring), 8 Report, 9 Client pack. All are built for the local Docker case; monitoring through Azure, Dynatrace or client APM is not built.
Runs go through `tools/runk6.py`, reports through `tools/report.py`, the pack through `tools/clientpack.py`.

## Rules (always)
1. Never invent a value. Business facts (purpose, scope, journeys, peak users, environment, owner) come only from sources or the user; ask for them with the realistic copy-paste examples from `python tools/brd.py questions`.
   Technical parameters clients rarely know (think time, traffic mix, targets, test types, abort limits, test windows) are advised with `python tools/brd.py advise` and written only after the user accepts them (`--apply`); they are recorded as Assumptions.
2. Every value you write into `brd.yaml` must be traceable: add a line to `evidence` (field + source file/page, or "user answer").
3. Clearly separate: stated (client said it), assumed (you or the user assume it; record under `risks` type Assumption), open (unanswered; record under `open_items`).
4. Never put real personal or payment data, passwords, tokens or API keys into any file. If a source contains them, tell the user and redact.
5. Requirements, BRD, catalogue-from-files and script steps never send requests. Only `tools/runk6.py` (and read-only browser discovery) may contact a system, and only the active environment in `environments.yaml`.
6. Do not decide or approve on the user's behalf (environment authorisation, accepting advised values, the run plan, approvals).
7. Discovery (browser/HAR) is read-only: never submit forms that create or change data, never use real credentials, and never send load. Only the user can approve a write action, per action, in chat or by listing it in the approved `run_plan.discovery_actions` in `environments.yaml`.
8. The API catalogue is built with `tools/catalogue.py` imports and `check`; never hand-parse Postman, OpenAPI or HAR files, and never store tokens, cookies or passwords in it.
9. The k6 script is generated from `brd.yaml` and `api-catalogue.yaml` using `.github/skills/k6-script-builder/`; it takes the host from `__ENV.BASE_URL`, has a smoke profile, a VU cap and abort thresholds, and must pass `python tools/k6check.py`. Generating a script never runs it.
10. Runs go only through `tools/runk6.py` (see `.github/skills/k6-run/`): smoke first, user counts and durations chosen by the user (in chat or in the approved `run_plan`), never raised by you, never retried after an abort, no `--force-step` without the user's explicit approval. The target and limits come from `environments.yaml` (`--env NAME` to pick one); never type a URL yourself. Run results are saved under `runs/<run-id>/` and never edited.
11. Environment facts (URL, owner, authorisation, limits, monitoring, test windows, test data, credential variable NAMES) live only in `environments.yaml`, never in `brd.yaml`. Never change an `authorisation` value yourself: only change it when the user states it in this chat, and then record their statement and the date in `authorisation_note`. Switch environments with `python tools/envconf.py use <project_dir> <name>`.
12. The execution report is produced only by `tools/report.py` (see `.github/skills/report-builder/`). Never edit `report.html` or any run file, never add conclusions or root causes by hand, and never describe a run below the peak load as meeting a requirement.
13. Server-side monitoring is collected only by `tools/runk6.py` through `tools/monitor.py` (see `.github/skills/monitoring-evidence/`). Never edit `monitoring.json`, never invent CPU or memory figures, and say plainly when a source (Azure, Dynatrace) is not built or a collection failed.
14. The client pack is built only by `tools/clientpack.py` (see `.github/skills/client-pack/`). Never send, upload or email it, never edit it, never change the BRD status yourself, and never copy secret-like text anywhere if the tool refuses.
15. To run the whole flow, follow `.github/skills/end-to-end/SKILL.md`: loop on `python tools/next.py <project>` (built on `tools/status.py`, the source of truth for which stage is done): it says PROCEED with one action or STOP at a human gate. Never clear a gate yourself. Never mark a stage done by hand, never skip one, and stop only at the human decisions the skill lists.
16. `/start-project` starts project setup and then continues the end-to-end loop until the client pack is built or a required human decision is reached. It asks business facts, advised values and the run plan in one message, then runs without stopping except for the decisions in the end-to-end skill.
17. After changing any file in `tools/`, `.github/` or `templates/`, run `python tools/lint.py` and `python -m unittest discover -s tests`, fix what they report, and show the user the result. Never weaken a test or a check to make it pass; tell the user instead.
18. Do not create extra documents (no status/decision/handoff logs; `docs/overview.md` is allowed). The only state files are `brd.yaml`, `environments.yaml`, `open-items.md`, `api-catalogue.yaml` and `STATE.md` inside the project folder. Keep `STATE.md` to about 8 lines.

## Where things live
- `templates/brd.template.yaml`: the BRD structure. Copy it, never edit it per project.
- `projects/<client>/<app>/sources/`: files the client gave us.
- `projects/<client>/<app>/brd.yaml`: the single source of truth for requirements.
- `projects/<client>/<app>/brd.md`: rendered from `brd.yaml` by the script. Never hand-edit it.
- `projects/<client>/<app>/api-catalogue.yaml`: the single source of truth for APIs; template `templates/api-catalogue.template.yaml`.
- `projects/<client>/<app>/environments.yaml`: every environment that may be tested and which one is active; template `templates/environments.template.yaml`; managed with `tools/envconf.py` (`check`, `show`, `use`).
- `tools/catalogue.py`: `import-postman`, `import-openapi`, `import-har`, and `check`. Always use it.
- `projects/<client>/<app>/k6/script.js` and `k6/requirement-map.yaml`: the generated script and its requirement-to-metric map.
- `projects/<client>/<app>/runs/<run-id>/`: `run.json` (UTC window, outcome), `summary.json`, `k6-output.txt`, `monitoring.json` (CPU and memory samples), `dashboard.html` (k6 charts, load runs) and `report.html` (the execution report).
- `projects/<client>/<app>/client-pack/`: the pack (`index.html` cover, `brd.html`, `runs/`, `manifest.json`) and its zip.
- `tools/lint.py`: checks the repo's own files (skill and prompt frontmatter, references, rule numbers). `tests/test_tools.py`: tests of the tools; run with `python -m unittest discover -s tests`.
- `tools/next.py`: the one next action and whether a human must decide first (gates). Exit 0 done, 1 proceed, 2 stop. Read-only.
- `tools/status.py`: shows which stages of a project are done and what is next. `tools/targetcheck.py`: checks that the target answers the catalogue's read calls (read-only, one request per API).
- `tools/clientpack.py`: builds the client pack. Always use it.
- `tools/monitor.py`: server-side CPU and memory sampling (`check` does a preflight sample). Used by runk6.
- `tools/report.py`: builds `report.html` for a run. Always use it.
- `tools/runk6.py`: runs k6 with the guards and records the run. Always use it.
- `tools/doctor.py`: checks this machine (Python, PyYAML, k6, pandoc, docker, repo files). Run it first; `setup.sh` / `setup.ps1` create `.venv` from `requirements.txt`.
- `tools/brdexport.py`: builds the Word file the client reviews and signs (`client-pack/brd-confirmation-v<version>.docx`) from `brd.yaml`: values with their basis, questions with an answer column, blank sign-off. Never edit the .docx, never fill its sign-off, never send it.
- `tools/k6check.py`: checks the script against the BRD and catalogue. Always use it.
- `tools/brd.py`: `check` lists missing must-have parameters; `questions` lists business facts to ask (with copy-paste examples); `advise` lists advised technical values and `--apply` writes them after the user accepts; `render` produces `brd.md`; `provenance` counts values as stated / advised / assumed / not evidenced / open. Always use it. Do not decide what is missing or format the BRD yourself.

## How to work
- `.github/agents/` holds optional specialist agents (`perf-orchestrator` hands stages to `perf-intake`, `perf-discovery`, `perf-scripter`, `perf-runner`). The runner has no edit tool on purpose. Skills and prompts work without them.
- Before the first command in a session, run `python tools/doctor.py` (repo root). If it reports a missing prerequisite, tell the user what to install and stop; do not work around it. In these instructions `python` means the repo's `.venv` Python; if plain `python` is missing or cannot import `yaml`, use `.venv/bin/python` (Windows: `.venv\Scripts\python`).
- Use the skills in `.github/skills/` for each step. Read the skill before starting.
- Ask everything you need in as few messages as possible: business facts, advised values to accept and the run plan together. Every example must be a realistic value the user can copy.
- EVERY question to the user, with no exception (choices, yes/no, gates, missing mappings, run counts, test data, monitoring), must include a ready copy-paste example answer the user can send back as the reply. For a gate use the `example reply` that `tools/next.py` prints. If a tool prints no example, write one yourself. Never ask a bare question.
- After every change to `brd.yaml`, run `python tools/brd.py check <path>` and report the result.
- Update `STATE.md` (stage, date, what is blocking) at the end of each step.
