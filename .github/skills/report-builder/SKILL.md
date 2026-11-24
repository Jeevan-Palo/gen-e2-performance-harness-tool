---
name: report-builder
description: Generate the HTML performance execution report for a recorded run from the k6 results, the BRD and the environment. Use for stage 8 (report) of the performance flow.
---

# Report builder (stage 8)

The report is built automatically by `tools/runk6.py` after every run. Use this skill only to rebuild or explain a report (for an older run, or after fixing an input). The report is produced only by `tools/report.py`. It reads the run files, `brd.yaml`, `environments.yaml` and `k6/requirement-map.yaml`, and writes `runs/<run-id>/report.html`. Every figure comes from the k6 files; nothing is typed by hand.

## Procedure
1. Ask which run if the user did not say, with a copy-paste example such as `latest load run`. Default: the latest load run of the active environment.
2. Run `python tools/report.py projects/<client>/<app> --run <run-id>` (omit `--run` for the latest load run).
3. Read the report back and tell the user in plain words:
   - the verdict banner (passed, not met, or not measured at peak load) and why,
   - each requirement result (Met, Not met, Not measured at peak load, Deferred),
   - p95 and p99 per transaction,
   - the limitations listed in section 5.
4. Tell the user where the file is (`runs/<run-id>/report.html`), that it opens in any browser, and that they can print it to PDF from there. If `dashboard.html` is in the same run folder, mention it for detailed k6 charts.
5. Update `STATE.md` (stage "10. Report", run id).

## If something in the report looks wrong
Fix the input (`brd.yaml`, `environments.yaml`, `k6/requirement-map.yaml`) and regenerate. Do not edit `report.html`, `summary.json`, `run.json` or `k6-output.txt`.

## Do not
- Do not add commentary, causes, recommendations or conclusions by hand. The report states facts only; analysis is a separate step the user asks for.
- Do not re-run a test to get a better number.
- Do not describe a run below the peak load as meeting a requirement. The tool marks those "Not measured at peak load"; keep that wording.
- Do not include secrets, tokens or credentials in anything you write.
