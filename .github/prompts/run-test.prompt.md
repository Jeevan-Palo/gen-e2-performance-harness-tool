---
mode: agent
description: Run the k6 test for a project (Step 8)
---
Run the performance test for the project I name (ask me which one if unclear), following `.github/skills/k6-run/SKILL.md`.

1. Do the preflight (k6 installed, the three checks pass).
2. Read profile parameters from the BRD. Ask me for an explicit load step or stress cap when required; do not invent values.
3. Run smoke first. If baseline is needed, run its specified repetitions, check consistency, and stop for my explicit sign-off before load.
4. Run only through `tools/runk6.py`; apply the selected profile's guards.
5. Tell me the outcome in plain words with p50/p90/p95/p99 per transaction, TPS, and the report path; wait for my instruction before another run.
