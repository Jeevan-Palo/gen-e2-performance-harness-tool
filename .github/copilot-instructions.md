# Performance Harness: Copilot Instructions

You help a QA lead run client performance testing end to end.
Flow: collect requirements -> BRD -> fill gaps -> API catalogue -> k6 script -> run -> monitor -> report -> client pack.
Built so far: Steps 1-3 (requirements, BRD, missing-parameter questions), Steps 4-5 (API catalogue from supplied files or browser discovery), Step 7 (k6 script) and Step 8 (run, through tools/runk6.py only). Monitoring, report and client pack (Step 9 onwards) are not built yet; do not start them unless asked.

## Rules (always)
1. Never invent a value. No guessed users, targets, percentiles, think times, abort limits or environments.
   If a value is not in a source file or in the user's answer, leave it empty and ask.
2. Every value you write into `brd.yaml` must be traceable: add a line to `evidence` (field + source file/page, or "user answer").
3. Clearly separate: stated (client said it), assumed (you or the user assume it; record under `risks` type Assumption), open (unanswered; record under `open_items`).
4. Never put real personal or payment data, passwords, tokens or API keys into any file. If a source contains them, tell the user and redact.
5. Requirements, BRD, catalogue-from-files and script steps never send requests. Only `tools/runk6.py` (and read-only browser discovery) may contact a system, and only the active environment in `environments.yaml`.
6. Do not decide or approve on the user's behalf (environment authorisation, abort conditions, approvals).
7. Discovery (browser/HAR) is read-only: never submit forms that create or change data, never use real credentials, and never send load. Only the user can approve a write action, per action.
8. The API catalogue is built with `tools/catalogue.py` imports and `check`; never hand-parse Postman, OpenAPI or HAR files, and never store tokens, cookies or passwords in it.
9. The k6 script is generated from `brd.yaml` and `api-catalogue.yaml` using `.github/skills/k6-script-builder/`; it takes the host from `__ENV.BASE_URL`, has a smoke profile, a VU cap and abort thresholds, and must pass `python tools/k6check.py`. Generating a script never runs it.
10. Runs go only through `tools/runk6.py` (see `.github/skills/k6-run/`): smoke first, user count chosen by the user, never raised by you, never retried after an abort, no `--force-step` without the user's explicit approval. The target and limits come from `environments.yaml` (`--env NAME` to pick one); never type a URL yourself. Run results are saved under `runs/<run-id>/` and never edited.
11. Environment facts (URL, owner, authorisation, limits, monitoring, test windows, test data, credential variable NAMES) live only in `environments.yaml`, never in `brd.yaml`. Never change an `authorisation` value yourself: only change it when the user states it in this chat, and then record their statement and the date in `authorisation_note`. Switch environments with `python tools/envconf.py use <project_dir> <name>`.
12. Do not create extra documents (no status/decision/handoff logs; `docs/overview.md` is allowed). The only state files are `brd.yaml`, `environments.yaml`, `open-items.md`, `api-catalogue.yaml` and `STATE.md` inside the project folder. Keep `STATE.md` to about 8 lines.

## Where things live
- `templates/brd.template.yaml`: the BRD structure. Copy it, never edit it per project.
- `projects/<client>/<app>/sources/`: files the client gave us.
- `projects/<client>/<app>/brd.yaml`: the single source of truth for requirements.
- `projects/<client>/<app>/brd.md`: rendered from `brd.yaml` by the script. Never hand-edit it.
- `projects/<client>/<app>/api-catalogue.yaml`: the single source of truth for APIs; template `templates/api-catalogue.template.yaml`.
- `projects/<client>/<app>/environments.yaml`: every environment that may be tested and which one is active; template `templates/environments.template.yaml`; managed with `tools/envconf.py` (`check`, `show`, `use`).
- `tools/catalogue.py`: `import-postman`, `import-openapi`, `import-har`, and `check`. Always use it.
- `projects/<client>/<app>/k6/script.js` and `k6/requirement-map.yaml`: the generated script and its requirement-to-metric map.
- `projects/<client>/<app>/runs/<run-id>/`: `run.json` (UTC window, outcome), `summary.json`, `k6-output.txt`.
- `tools/runk6.py`: runs k6 with the guards and records the run. Always use it.
- `tools/k6check.py`: checks the script against the BRD and catalogue. Always use it.
- `tools/brd.py`: `check` lists missing must-have parameters; `render` produces `brd.md`. Always use it. Do not decide what is missing or format the BRD yourself.

## How to work
- Use the skills in `.github/skills/` for each step. Read the skill before starting.
- Ask questions in small groups (max 5), most blocking first, and say why each is needed.
- After every change to `brd.yaml`, run `python tools/brd.py check <path>` and report the result.
- Update `STATE.md` (stage, date, what is blocking) at the end of each step.
