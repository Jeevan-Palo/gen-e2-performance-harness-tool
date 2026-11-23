---
mode: agent
description: Generate the HTML execution report for a run (Step 10)
---
Generate the performance execution report for the project and run I name (ask me which one if unclear), following `.github/skills/report-builder/SKILL.md`.

1. Run `python tools/report.py <project folder> --run <run id>` (latest load run if I give no run).
2. Tell me in plain words: the verdict and RAG, each requirement result, p50/p90/p95/p99 per transaction, TPS, saturation observation, run comparison, coverage, exit-criteria status, and limitations.
3. Tell me where `report.html` is and how to open it. Do not edit the report or any run file by hand.
