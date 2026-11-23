---
name: requirements-intake
description: Read client requirement files (BRD, emails, notes, spreadsheets) and extract them into brd.yaml without inventing anything. Then ask the client only for business facts and offer advised values for technical parameters. Use for Steps 1 and 3 of the performance flow.
---

# Requirements intake (Steps 1 and 3)

## Inputs
Everything in `projects/<client>/<app>/sources/`. If it is empty, stop and ask the user to add files.

## Procedure
1. List every file in `sources/`. Read each one fully (PDF, Word, Markdown, text, CSV). If a file cannot be read, say so and ask for another format.
2. Check for secrets (passwords, tokens, API keys, card numbers, real personal data). If found: do not copy them anywhere, tell the user which file, and continue without them.
3. Environment facts (URL, owner, authorisation, limits, monitoring, test windows, test data) go into `environments.yaml` (one block per environment), never into `brd.yaml`. Ask the user for the environment URL; never guess it. Credentials are never stored: list only environment variable NAMES.
   Extract everything else into `brd.yaml` (structure is in `templates/brd.template.yaml`):
   - Copy only what the sources state. Keep the client's wording for vague statements (e.g. "should be responsive") and do not make it measurable yourself; add an open item instead.
   - Do not convert or derive figures (e.g. do not turn 1,200 orders/day into TPS).
   - For each value, add an entry to `evidence`: `{field: "workload.peak_concurrent_users", source: "client_brd.pdf p.3"}`.
   - If sources conflict, keep both in `open_items` as a question; do not pick one.
4. Run `python tools/brd.py check projects/<client>/<app>/brd.yaml`. It prints the missing must-have parameters. Treat that list as the authority.
5. Ask everything in ONE message, in two parts:
   - **Business facts** from `python tools/brd.py questions <brd.yaml>`: only things the client knows (purpose, scope, journeys, peak users, environment owner). Show each question with its copy-paste example exactly as the tool prints it. Never ask a field already in `brd.yaml`, `environments.yaml` or a source, and never turn template placeholder text into a question.
   - **Advised values** from `python tools/brd.py advise <brd.yaml>`: technical parameters clients rarely know (think time, traffic mix, measurement points, targets, test types, abort limits, test windows, test data). Show them as a table and say: "Reply 'accept' or change any row."
   - In the same message ask for the run plan (see the `end-to-end` skill), so the rest of the flow does not stop again.
6. When the user answers:
   - Write each stated business fact with `evidence` source "user answer, <date>". If a fact is unknown, add one open item for it; if it is peak users, re-run `advise`, which then offers the environment limit as the advised peak.
   - On "accept" run `python tools/brd.py advise <brd.yaml> --apply` (use `--skip=key,...` for rows the user changed, then write those values as user answers). The tool records evidence and one Assumption risk; never apply advice without the user's acceptance.
   - Re-run `check`. Do not ask the same field again. If gaps remain only because facts are unknown and the user wants to go on, set `meta.open_items_decision: proceed_with_open_items` with evidence and leave `meta.status: Draft`.
7. Anything the user cannot answer yet goes in `open_items` with an owner if known. Do not fill it in.

## Output
Updated `brd.yaml` and a short summary: what was found, what is missing, what is open. Then continue with the `brd-builder` skill.
