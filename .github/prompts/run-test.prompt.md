---
mode: agent
description: Run the k6 test for a project (Step 8)
---
Run the performance test for the project I name (ask me which one if unclear), following `.github/skills/k6-run/SKILL.md`.

1. Do the preflight (k6 installed, the three checks pass).
2. Ask me for the number of users and durations if I did not give them.
3. Run smoke first, then the load run I asked for, only through `tools/runk6.py`.
4. Tell me the outcome in plain words with p95 and p99 per transaction, and wait for my instruction before doing anything else.
