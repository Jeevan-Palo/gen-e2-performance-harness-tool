---
name: requirements-intake
description: Read client requirement files (BRD, emails, notes, spreadsheets) and extract them into brd.yaml without inventing anything. Then list and ask for missing parameters. Use for Steps 1 and 3 of the performance flow.
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
5. Ask the user for the missing items:
   - Group into at most 5 questions per message, most blocking first.
   - For each, say what is missing, why it matters for the test, and give an example format (e.g. "p95 or p99?").
   - Never suggest a default as if it were agreed. You may offer an example, labelled as an example.
6. When the user answers: write the value, add `evidence` with source "user answer, <date>", re-run `check`. Repeat until it reports no missing must-haves, or the user says to proceed with open items.
7. Anything the user cannot answer yet goes in `open_items` with an owner if known. Do not fill it in.

## Output
Updated `brd.yaml` and a short summary: what was found, what is missing, what is open. Then continue with the `brd-builder` skill.
