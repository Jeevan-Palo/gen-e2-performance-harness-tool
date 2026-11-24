---
name: api-source-selector
description: Ask which source the API catalogue should be built from (Postman collection, OpenAPI/Swagger, API list document, HAR recording or browser discovery) and hand over to the matching skill. Use first for stage 3 (catalogue) of the performance flow.
---

# Choose the API source (stage 3)

One source per run. If more is needed later (for example browser discovery for gaps), run this skill again.

## Procedure
1. Read `brd.yaml` and `STATE.md`. Stop if `python tools/brd.py check <brd.yaml>` still reports missing must-haves.
2. List `sources/` and propose the likely source, by content:
   - JSON with `info.schema` containing `getpostman.com`: Postman collection (a JSON with a `values` list is its environment file).
   - JSON/YAML with `openapi` or `swagger`: OpenAPI/Swagger.
   - `.har`: HAR recording.
   - Word, PDF, Excel or text listing endpoints: API list document.
   - Nothing usable: ask the user.
3. Ask the user to choose one (use the ask tool; mark the detected one as the default):
   - Postman collection
   - OpenAPI / Swagger
   - API list document
   - HAR recording
   - Browser discovery (no documentation)
4. Follow the matching skill:

   | Choice | Skill |
   |---|---|
   | Postman collection | `.github/skills/api-catalogue-from-postman/SKILL.md` |
   | OpenAPI / Swagger, API list document | `.github/skills/api-catalogue-from-sources/SKILL.md` |
   | HAR recording, browser discovery | `.github/skills/api-discovery-browser/SKILL.md` |

5. Record the chosen source in `STATE.md` (one line). Do not create other documents.

## Do not
- Do not pick a source for the user when `sources/` holds several kinds: ask.
- Do not send any request here; only the discovery skill may browse, and only as its own rules allow.
