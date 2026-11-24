---
name: brd-builder
description: Turn brd.yaml into the structured Business Requirements Document for performance testing (same sections as the standard BRD template), track open items and version it. Use for stage 1 (BRD) of the performance flow, after requirements-intake.
---

# BRD builder (stage 1)

## Procedure
1. Make sure `brd.yaml` exists in the project folder and has been through `requirements-intake`.
2. Run `python tools/envconf.py check <project>` and `python tools/brd.py check <brd.yaml>` and show the results. Section 8 of the BRD is rendered from the active environment in `environments.yaml`; to change it, edit that file (or switch with `python tools/envconf.py use`), not `brd.yaml`.
3. Run `python tools/brd.py render <brd.yaml>`. This writes `brd.md` next to it with the standard sections:
   1 Purpose, 2 Objectives and scope, 3 Stakeholders, 4 Business transactions, 5 Workload model, 6 Performance requirements, 7 Test types, 8 Environment and data, 9 Abort conditions, 10 Monitoring and reporting, 11 Assumptions/constraints/dependencies/risks, 12 Acceptance and exit criteria, 13 Open items, 14 Approval.
   Missing values appear as `[NOT PROVIDED]`. Do not edit `brd.md` by hand; fix `brd.yaml` and render again.
4. Write `open-items.md`: one line per missing must-have (from `check`) and per entry in `open_items`, with owner and due date if known.
5. Version: set `meta.status` to "Draft" and keep `meta.version` at 0.x while must-haves are missing. Only set "In review" when `check` passes and the user confirms. Never set "Approved": only the client's business owner approves.
6. Client confirmation: run `python tools/brd.py provenance <brd.yaml>` and show the counts, then `python tools/brdexport.py <project>`. It writes `client-pack/brd-confirmation-v<version>.docx` (Word): every value with its basis (Stated / Advised / Assumed / Not evidenced / Open) and source, the open questions with an answer column, and a blank sign-off table. Tell the user which file it is and that it is for the client to review, answer and sign. When the client returns it, record their answers in `brd.yaml` with evidence "client confirmation document, <date>" and ask the user before changing any status or approval.
7. Update `STATE.md`: stage, date, number of missing must-haves, number of open items.
8. Tell the user: here is `brd.md`, here is what is still missing, please review before it goes to the client.

## Do not
- Do not add requirements, targets or sections that the sources and user answers do not support.
- Do not fill the Approval table.
- Do not produce PDF or Word by retyping the content. Word comes only from `tools/brdexport.py`.
- Do not fill the sign-off table of the Word file, edit the .docx, or send it.
