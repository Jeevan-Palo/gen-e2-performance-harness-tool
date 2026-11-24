---
mode: agent
description: Build the API catalogue for a project (stage 3)
---
Build the API catalogue for the project I name (ask me which one if unclear).

1. Read `brd.yaml` and `STATE.md`. Do not continue if `python tools/brd.py check` still reports missing must-haves; tell me instead.
2. Follow `.github/skills/api-source-selector/SKILL.md`: ask me which source to use (Postman collection, OpenAPI/Swagger, API list document, HAR recording or browser discovery), then follow the skill it names.
3. Ask me questions in groups of at most 5, each with a copy-paste example answer, and wait for answers. Never guess. Finish when `python tools/catalogue.py check` passes or I say to proceed.
