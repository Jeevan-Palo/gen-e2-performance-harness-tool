# Performance Testing Harness

## One-time setup
1. Create a new empty repo and copy these files in (keep the folder structure).
2. `python -m pip install -r requirements.txt`
3. Open the repo in VS Code with GitHub Copilot Chat. Use Agent mode.
   If the skills are not picked up, check that Copilot agent skills / prompt files are enabled in your VS Code settings.
4. Test the script: `python tools/brd.py check projects/_example/brd.yaml` (should list missing items).

## Use it
1. In Copilot Chat (Agent mode) type `/start-project` and answer the client and application name.
2. Put the client's files in `projects/<client>/<app>/sources/`.
3. Tell Copilot: "Sources are ready. Run requirements-intake, then brd-builder."
4. Answer its questions. It stops when `tools/brd.py check` reports no missing must-haves or you tell it to proceed with open items.
5. Review `brd.md` and `open-items.md` before anything goes to the client.

## Environments
Each project has `environments.yaml`: one block per environment (local, test, public, ...) with URL, owner, authorisation, limits, monitoring and test windows. Switch with `python tools/envconf.py use <project_dir> <name>`, and validate with `python tools/envconf.py check <project_dir>`. Runs are refused on an environment whose authorisation is `not_confirmed`.

## Steps 4-5: API catalogue
1. In Copilot Chat (Agent mode) type `/build-catalogue` and name the project.
2. Put API files (Postman collection, OpenAPI/Swagger, API list document, or a HAR recording) in `sources/` first if you have them.
3. Answer its questions. It finishes when `python tools/catalogue.py check` passes.

## Step 7: k6 script
1. Install k6 on your machine (macOS: `brew install k6`).
2. In Copilot Chat (Agent mode) type `/build-script` and name the project. The profile library supports baseline, stepped ramp, stress, spike and endurance; each needed profile selects catalogue flow IDs in `brd.yaml`. It writes `k6/script.js` and `k6/requirement-map.yaml`, then runs `python tools/k6check.py <project folder>`.
3. It does not run the script. Running is the next step.

## Step 8: run
Use only `tools/runk6.py`. Run smoke first. If baseline is needed, run its BRD-defined repetitions, then run `python tools/baseline.py check <project>`; review the metrics and record human approval with `python tools/baseline.py sign-off <project> --by "<approver>" --date YYYY-MM-DD`. Consistency uses the coefficient of variation across common measured metrics and must be strictly below the BRD limit. A stepped ramp is blocked until that baseline is signed off. Choose `--vus` from the BRD step list; the 2x rule applies to ramp steps only. Stress, spike and endurance use their BRD parameters and profile-specific safety/window guards. Each run records profile parameters and selected flow IDs.

## Step 10: report
The report is built automatically after every run: `runs/<run-id>/report.html` (add `--open` to `runk6.py` to open it in the browser). It includes p50/p90/p95/p99, TPS, errors, CPU/memory, DB metrics when collected (otherwise explicitly "not collected"), strict RAG, saturation observations, same-profile run comparisons, profile-by-flow coverage and exit-criteria status. Findings contain generated observations/evidence; layer, hypothesis and finding text appear only when recorded in the BRD with human approval details.
In Copilot Chat (Agent mode) type `/build-report` and name the project (and a run id, or it uses the latest load run). It writes `runs/<run-id>/report.html`. Open it in a browser (macOS: `open <path>`); print to PDF from there. Or run it yourself: `python tools/report.py projects/<client>/<app> --run <run-id>`.

## Step 9: monitoring
Set `monitoring` in `environments.yaml`: for a local Docker app `{source: docker_stats, containers: [<container names>], interval_seconds: 5}` (list names with `docker ps`). Check it with `python tools/monitor.py check projects/<client>/<app>`. Every run then saves `monitoring.json` (CPU and memory of those containers and of k6). Azure, Dynatrace and client APM collectors are not built; add a provider only when a real project identifies it and supplies access details.

## Step 11: client pack
In Copilot Chat (Agent mode) type `/build-pack` and name the project, or run `python tools/clientpack.py projects/<client>/<app>` (add `--open` to open the cover). It writes `client-pack/<app>-<run-id>/` with `index.html` (cover summary, coverage matrix, exit-criteria status), `brd.html`, reports and evidence, and `manifest.json`, plus a `.zip`. `--run` accepts only a passed load run. It refuses if the BRD has missing must-haves, if no passed load run exists, or if secret-like text is found. It never sends anything.

## Start here
New project: in Copilot Chat (Agent mode) type `/run-end-to-end`. It runs `python tools/status.py <project>`, does the next unfinished stage, and stops only where you must decide (missing requirement values, environment and authorisation, write actions, how many users to run, sharing the pack). To see where any project stands, or to resume after a break: `python tools/status.py projects/<client>/<app>`.
Stage 4 is a read-only check that the target answers the catalogue's calls: `python tools/targetcheck.py projects/<client>/<app>` (one request per eligible read API, no writes, no logins). It binds the result to the active base URL, blocks redirects outside that exact origin, URL-encodes required query parameters, and compares observed status and response fields with the catalogue.

## Checking the harness itself
Dependencies are pinned in `requirements.txt`; GitHub Actions runs lint and tests on pushes and pull requests. After any change to the tools, skills, prompts or instructions: `python tools/lint.py` and `python -m unittest discover -s tests` (tests that need k6 are skipped if k6 is missing). Both must pass before you rely on a change.
