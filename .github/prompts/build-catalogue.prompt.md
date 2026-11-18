---
mode: agent
description: Build the API catalogue for a project (Steps 4-5)
---
Build the API catalogue for the project I name (ask me which one if unclear).

1. Read `brd.yaml` and `STATE.md`. Do not continue if `python tools/brd.py check` still reports missing must-haves; tell me instead.
2. Look in `sources/` for API files (Postman collection, OpenAPI/Swagger, API list documents, HAR files).
3. If supplied sources exist, follow `.github/skills/api-catalogue-from-sources/SKILL.md`.
4. If something is missing, or no API sources exist, ask me whether to discover it in the browser or whether I will record a HAR file, then follow `.github/skills/api-discovery-browser/SKILL.md`.
5. Ask me questions in groups of at most 5 and wait for answers. Never guess. Finish when `python tools/catalogue.py check` passes or I say to proceed.
