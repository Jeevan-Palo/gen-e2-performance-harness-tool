---
name: monitoring-evidence
description: Collect server-side CPU and memory evidence during a run, from the monitoring source set in environments.yaml (docker_stats is built; Azure, Dynatrace and client APM are not built yet). Use during stage 7 (load runs) of the performance flow.
---

# Monitoring evidence (stage 7)

Monitoring is collected automatically by `tools/runk6.py` while a run is in progress. The source comes from `environments.yaml` (`monitoring.source`) of the active environment. The data is saved as `runs/<run-id>/monitoring.json` and appears in section 4 of `report.html`.

## Sources
- `docker_stats` (built): samples CPU and memory of the listed Docker containers (`monitoring.containers`, every `interval_seconds`) and of k6 itself, so we can tell whether the load generator was the bottleneck. CPU % follows Docker: 100% = one core.
- `azure`, `dynatrace`, `client_apm` (NOT built yet): `runk6.py` says so and collects nothing. Do not pretend otherwise and never invent CPU or memory figures. These sources need a post-run query for the run's exact UTC window (`run.json` has `start_utc` and `end_utc`).
- `none`: nothing is collected; the report says so.

## Before a run (docker_stats)
1. Run `python tools/monitor.py check projects/<client>/<app>`. It prints one sample per configured container.
2. If it reports a problem (Docker not running, container name wrong), tell the user and stop. Do not start the run unless the user says to continue without monitoring.

## After a run
Read the `MONITORING:` line of the runk6 output. Tell the user: samples collected, or why not. The report is built automatically.

## Adding Azure or Dynatrace later
Ask the user for: the resource names or entity ids to watch, the metrics, and how access is granted. Credentials are never written to any file: only environment variable NAMES go in `environments.yaml`. A new collector must write the same `monitoring.json` structure so the report works unchanged.

## Do not
- Do not edit `monitoring.json` or any run file.
- Do not describe CPU or memory results as healthy or unhealthy by yourself; state the figures and the limits in the report.
- Do not collect from systems the user has not named.
