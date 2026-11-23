# perf-harness (Steps 1-3: requirements, BRD, missing parameters)

## One-time setup
1. Create a new empty repo and copy these files in (keep the folder structure).
2. `pip install pyyaml`
3. Open the repo in VS Code with GitHub Copilot Chat. Use Agent mode.
   If the skills are not picked up, check that Copilot agent skills / prompt files are enabled in your VS Code settings.
4. Test the script: `python tools/brd.py check projects/_example/brd.yaml` (should list missing items).

## Use it
1. In Copilot Chat (Agent mode) type `/start-project` and answer the client and application name.
2. Put the client's files in `projects/<client>/<app>/sources/`.
3. Confirm the source files are ready and provide the environment details if requested.
4. `/start-project` continues the end-to-end flow through catalogue, script, smoke/load, report and client pack. It stops for human decisions, as listed by `end-to-end`.
5. Answer one message: the business facts the client knows (each question has a copy-paste example), reply `accept` to the advised technical values (think time, traffic mix, targets, abort limits, test windows), and approve the run plan (load steps, durations, discovery actions, build the pack if targets are missed). After that the flow runs to the client pack, stopping only for authorisation, a failed smoke run, an aborted run or something outside the plan.

## Environments
Each project has `environments.yaml`: one block per environment (local, test, public, ...) with URL, owner, authorisation, limits, monitoring and test windows. Switch with `python tools/envconf.py use <project_dir> <name>`, and validate with `python tools/envconf.py check <project_dir>`. Runs are refused on an environment whose authorisation is `not_confirmed`.

## Steps 4-5: API catalogue
1. In Copilot Chat (Agent mode) type `/build-catalogue` and name the project.
2. Put API files (Postman collection, OpenAPI/Swagger, API list document, or a HAR recording) in `sources/` first if you have them.
3. Answer its questions. It finishes when `python tools/catalogue.py check` passes.

## Step 7: k6 script
1. Install k6 on your machine (macOS: `brew install k6`).
2. In Copilot Chat (Agent mode) type `/build-script` and name the project. It writes `k6/script.js` and `k6/requirement-map.yaml`, then runs `python tools/k6check.py <project folder>`.
3. It does not run the script. Running is the next step.

## Step 8: run
In Copilot Chat (Agent mode) type `/run-test`, name the project and the number of users. It runs smoke first, then the load test, only through `tools/runk6.py`, and saves each run under `runs/`.

## Step 10: report
The report is built automatically after every run: `runs/<run-id>/report.html` (add `--open` to `runk6.py` to open it in the browser). The rest of this section is for rebuilding one by hand.
In Copilot Chat (Agent mode) type `/build-report` and name the project (and a run id, or it uses the latest load run). It writes `runs/<run-id>/report.html`. Open it in a browser (macOS: `open <path>`); print to PDF from there. Or run it yourself: `python tools/report.py projects/<client>/<app> --run <run-id>`.

## Step 9: monitoring
Set `monitoring` in `environments.yaml`: for a local Docker app `{source: docker_stats, containers: [<container names>], interval_seconds: 5}` (list names with `docker ps`). Check it with `python tools/monitor.py check projects/<client>/<app>`. Every run then saves `monitoring.json` (CPU and memory of those containers and of k6) and the report shows it in section 4. Azure, Dynatrace and client APM collectors are not built yet.

## Step 11: client pack
In Copilot Chat (Agent mode) type `/build-pack` and name the project, or run `python tools/clientpack.py projects/<client>/<app>` (add `--open` to open the cover). It writes `client-pack/<app>-<run-id>/` with `index.html` (cover summary), `brd.html`, every run's report and evidence, and `manifest.json`, plus a `.zip`. It refuses if the BRD has missing must-haves, if no passed load run exists, or if secret-like text is found. It never sends anything.

## Start here
New project: in Copilot Chat (Agent mode) type `/run-end-to-end`. It runs `python tools/status.py <project>`, does the next unfinished stage, and stops only where you must decide (missing requirement values, environment and authorisation, write actions, how many users to run, sharing the pack). To see where any project stands, or to resume after a break: `python tools/status.py projects/<client>/<app>`.
Stage 4 is a read-only check that the target answers the catalogue's calls: `python tools/targetcheck.py projects/<client>/<app>` (one request per read API, no writes, no logins).

## Checking the harness itself
After any change to the tools, skills, prompts or instructions: `python tools/lint.py` (repo files are consistent) and `python -m unittest discover -s tests` (tools behave; tests that need k6 are skipped if k6 is missing). Both must pass before you rely on a change.
