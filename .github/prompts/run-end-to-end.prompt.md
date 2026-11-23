---
mode: agent
description: Start or continue the whole performance-testing flow for a project
---
Run the whole performance-testing flow for the project I name (ask me which one if unclear; if it is new, do `/start-project` first), following `.github/skills/end-to-end/SKILL.md`.

1. Run `python tools/status.py <project folder>` and tell me where the project stands.
2. Do the next stage with the skill or tool the end-to-end skill names, then run status again. Keep going until all stages are done or you need a decision from me.
3. Stop and ask me at every decision point the skill lists. Never guess a value and never decide authorisation for me.
4. For BRD gaps, use `python tools/brd.py questions <brd.yaml>`; ask only those fields, no template placeholders, and no repeated questions. Mark unknown answers open and proceed.
