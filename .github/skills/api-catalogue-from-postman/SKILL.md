---
name: api-catalogue-from-postman
description: Build the API catalogue (api-catalogue.yaml) from a client-supplied Postman collection and optional Postman environment file, using the expected statuses, response fields and token correlation stated in the collection's test scripts. Use for stage 3 (catalogue) when the API source is a Postman collection.
---

# API catalogue from a Postman collection (stage 3)

Output: `projects/<client>/<app>/api-catalogue.yaml` (structure in `templates/api-catalogue.template.yaml`). Reading files only: never send a request, never run the collection.

## Procedure
1. If `api-catalogue.yaml` does not exist, copy the template. Read `brd.yaml` for the transaction ids.
2. Find the collection (and the environment export, if any) in `sources/`. Import with the script, never by hand:
   `python tools/catalogue.py import-postman <catalogue> <collection.json> [environment.json]`
3. What the import takes from the collection (only what it literally states):
   - Method, path, query, headers (secret-looking ones dropped), body (sensitive values `<redacted>`), folder as `business_flow`.
   - From each request's test script: `response.status` (first expected status; all in `expected_statuses`), `content_type`, top-level `fields`, and the response-time limit as a note. These are expected, not observed: the note says so and `confidence` stays `medium`.
   - Variables set by a test script (`pm.environment.set('token', ...)`) and used as `{{token}}` by another request become `dynamic_values` and `depends_on`. A variable nothing sets becomes a catalogue note: ask the user where it comes from.
   - From the environment file: variable names and a non-secret `base_url`. Values of secret-looking variables are never read.
   - Requests whose script expects only 4xx (negative tests) go in after the positive ones. One on a route already imported is not a separate API; it is listed under `notes`. One on a new route is imported with `negative_test: true` and must not go into a load flow.
4. Then follow steps 3-6 of the `api-catalogue-from-sources` skill (map `transaction` and `step_order`, `flows`, `safe_to_load`, `side_effects`, `test_data`, then `python tools/catalogue.py check <catalogue> <brd.yaml>` and `STATE.md`). Ask the user for every mapping and `safe_to_load` value you cannot take from a source, each with a copy-paste example such as `login -> transaction T1, step 1, safe_to_load: false`.

## Do not
- Do not copy tokens, cookies, passwords or API keys from the collection or environment file into any file.
- Do not treat the script's response-time limit as a BRD requirement or the expected status as a confirmed one.
- Do not change a `safe_to_load` or `side_effects` value because a request looks harmless.
