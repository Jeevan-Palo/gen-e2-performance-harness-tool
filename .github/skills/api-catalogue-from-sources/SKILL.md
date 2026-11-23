---
name: api-catalogue-from-sources
description: Build the API catalogue (api-catalogue.yaml) from documents the client supplied, such as a Postman collection, an OpenAPI or Swagger file, or an API list in a document. Maps each API to the BRD transactions. Use for Step 4 of the performance flow.
---

# API catalogue from supplied sources (Step 4)

Output: `projects/<client>/<app>/api-catalogue.yaml` (structure in `templates/api-catalogue.template.yaml`).

## Procedure
1. If `api-catalogue.yaml` does not exist, copy the template. Read `brd.yaml` for the transaction ids (T1, T2, ...).
2. List the API files in `sources/`. For each, use the script (never hand-parse):
   - Postman collection: use the `api-catalogue-from-postman` skill instead (it also reads test scripts and the environment file).
   - OpenAPI/Swagger: `python tools/catalogue.py import-openapi <catalogue> <file> [base_url]`
   - API list in a Word/PDF/Excel/text document: read it and add entries by hand, with `evidence.source_type: document`, the file and page as `source`, and `confidence: medium` or `low`.
3. Fill what the import cannot know, using only the sources or the user's answers:
   - `meta.application` and `meta.base_url` if empty.
   - `transaction` and `step_order` for every API (map to BRD transaction ids). If the mapping is unclear, ask the user; do not guess.
   - `dynamic_values` (tokens, ids, CSRF values returned by one call and used by another) and `depends_on`.
   - `safe_to_load`, `side_effects`, `test_data`. Calls that create data, send email, take payment, or call third parties must not be `yes` without evidence. Mark them `conditional` or `no` and tell the user.
   - `flows`: the ordered API ids for each BRD transaction.
4. Redact: never write tokens, passwords, cookies, API keys or real personal data. Use `<redacted>` or `${ENV_VAR}` names.
5. Run `python tools/catalogue.py check <catalogue> <brd.yaml>`. Fix every issue you can from the sources; ask the user for the rest (max 5 questions per message, most blocking first). Repeat until it reports OK or the user says to proceed.
6. Update `STATE.md` (stage "4. API catalogue", date, open issues). Do not write any performance script yet.

## Do not
- Do not call any API or any client system in this skill. Reading documents only.
- Do not invent endpoints, fields or example values that are not in a source.
- Do not drop an API because it looks unimportant; map it or list it under `notes`.
