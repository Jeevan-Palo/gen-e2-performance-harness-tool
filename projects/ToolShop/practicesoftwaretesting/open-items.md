# Open items: Practice Software Testing - Toolshop v5.0

Generated from brd.yaml. Nothing below was guessed; each item needs an answer.

Missing must-have parameters (`tools/brd.py check`): 0

1. Resolved for now: load runs target the test lead's own local Docker copy instead of the public site, so Testsmith's authorisation is not needed for this phase. Revisit only if testing against the public site is wanted again. (owner: Test lead, status: Resolved)
2. Base URL confirmed (http://localhost:8091). Still open: confirm that the local Docker copy's REST API matches api-catalogue.yaml (built from discovery against the public site, same paths/methods incl. QUERY) before relying on its results. (owner: Test lead, status: Open)
3. Confirm how many test accounts are available and whether one account can be used by several virtual users at once. (owner: Test lead, status: Open)
4. Whether the site's checkout accepts dummy/test payment details for practice has not been verified. (owner: Test lead, status: Open)
5. Which further test types (stress, spike, soak, scalability) are needed in addition to Baseline and Load, which are confirmed as yes? (owner: Test lead, status: Open)
