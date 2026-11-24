---
name: client-pack
description: Build the client pack (cover summary, BRD as HTML, every run's report and the evidence files, manifest and zip) from a finished project. Use for stage 9 (client pack) of the performance flow. Never sends anything.
---

# Client pack (stage 9)

The pack is built only by `tools/clientpack.py`. It writes `projects/<client>/<app>/client-pack/<app>-<run-id>/` (open `index.html`) and a `.zip` next to it. It sends nothing anywhere.

## Procedure
1. Check that the BRD and a passed load run exist: `python tools/brd.py check` and the `runs/` folder. If the BRD has missing must-haves, the tool refuses; tell the user what is missing.
2. Ask the user which run to base the pack on if they care (with a copy-paste example such as `use the default run`); by default the tool picks the passed load run with the most users (preferring one at or above the BRD peak).
3. Run `python tools/clientpack.py projects/<client>/<app> [--run <run-id>]`.
4. Tell the user in plain words: the verdict on the cover, which run it is based on, how many runs are included, and every `WARNING:` line (for example: BRD status is Draft; `prepared_by` is empty).
5. Give the user the path of `index.html` and the `.zip`. Remind them to read the cover page and the "What this result does and does not show" section before sharing.
6. Update `STATE.md` (stage "11. Client pack", pack path).

## Rules
- Never send, upload or email the pack. Sharing is the user's decision.
- Never edit files inside the pack, and never change the BRD status yourself (only the user decides "In review"; only the client's business owner approves).
- If the tool refuses because of secret-like text, tell the user which file, do not copy or print the text, and let them clean the source.
- Do not add conclusions, causes or recommendations by hand.
