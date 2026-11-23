---
name: brd-builder
description: Turn brd.yaml into the structured Business Requirements Document for performance testing (same sections as the standard BRD template), track open items and version it. Use for Step 2 of the performance flow.
---

# BRD builder (Step 2)

## Procedure
1. Make sure `brd.yaml` exists in the project folder and has been through `requirements-intake`.
2. Run `python tools/envconf.py check <project>` and `python tools/brd.py check <brd.yaml>` and show the results. Section 8 of the BRD is rendered from the active environment in `environments.yaml`; to change it, edit that file (or switch with `python tools/envconf.py use`), not `brd.yaml`.
3. Run `python tools/brd.py render <brd.yaml>`. This writes `brd.md` next to it with the standard sections:
   1 Purpose, 2 Objectives and scope, 3 Stakeholders, 4 Business transactions, 5 Workload model, 6 Performance requirements, 7 Test types and selected profile parameters, 8 Environment and data, 9 Abort conditions and operational safety contacts, 10 Monitoring, reporting and the fixed RAG policy, 11 Assumptions/constraints/dependencies/risks, 12 Per-profile entry and exit criteria, 13 Open items, 14 Approval.
   Missing values appear as `[NOT PROVIDED]`. Do not edit `brd.md` by hand; fix `brd.yaml` and render again.
4. Write `open-items.md`: one line per missing must-have (from `check`) and per entry in `open_items`, with owner and due date if known.
   Profile fields are required only when that test profile is marked `needed: yes`. For Stress and Spike, resolve the abort/rollback owners, rollback procedure and on-call contact before considering the BRD complete. RAG uses the fixed harness definitions; exact BRD targets determine requirement outcomes, and no numeric amber tolerance is assumed.
5. Version: set `meta.status` to "Draft" and keep `meta.version` at 0.x while must-haves are missing. Only set "In review" when `check` passes and the user confirms. Never set "Approved": only the client's business owner approves.
6. Update `STATE.md`: stage, date, number of missing must-haves, number of open items.
7. Tell the user: here is `brd.md`, here is what is still missing, please review before it goes to the client.

## Do not
- Do not add requirements, targets or sections that the sources and user answers do not support.
- Do not fill the Approval table.
- Do not produce PDF or Word by retyping the content. If PDF/Word is wanted, convert the rendered `brd.md` (e.g. with pandoc if installed) and say so.
