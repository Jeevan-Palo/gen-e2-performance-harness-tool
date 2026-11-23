---
mode: agent
description: Generate the k6 script for a project (Step 7)
---
Build the k6 script for the project I name (ask me which one if unclear).

1. Run `python tools/brd.py check` and `python tools/catalogue.py check` for the project. If either reports issues, stop and tell me.
2. Follow `.github/skills/k6-script-builder/SKILL.md`, starting from `reference-skeleton.js`.
3. Run `python tools/k6check.py <project folder>` and fix issues until it says OK.
4. Do not run k6 and do not send any requests. Show me the `tools/runk6.py --profile smoke` command, and a short summary: profiles, selected flows, mix, thresholds, abort rules.
5. If something needed is missing or unclear (for example a test data source), ask me; never guess.
