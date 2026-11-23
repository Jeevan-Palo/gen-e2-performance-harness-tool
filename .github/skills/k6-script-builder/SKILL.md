---
name: k6-script-builder
description: Generate a k6 performance script from brd.yaml and api-catalogue.yaml, with thresholds, abort rules and a requirement map for the report. Use for Step 7 of the performance flow. Does not run the script.
---

# k6 script builder (Step 7)

Inputs: `projects/<client>/<app>/brd.yaml` and `api-catalogue.yaml`. Both checks must pass first:
`python tools/brd.py check <brd.yaml>` and `python tools/catalogue.py check <catalogue>`. If not, stop and tell the user.
Outputs: `projects/<client>/<app>/k6/script.js` and `k6/requirement-map.yaml`.

The catalogue's separate `web_tier.requests` inventory is discovery metadata only; do not treat it as executable flow steps in this release.

Start from `.github/skills/k6-script-builder/reference-skeleton.js` (tested). Keep its structure and guards; adapt CONFIG, MIX and the transaction functions.

## Procedure
1. Read the BRD: active transactions, traffic shares, think time, each needed profile and its parameters, requirements, abort conditions. Requirements whose notes say "deferred" are skipped.
2. Read the catalogue: for each active transaction, follow `flows` order. APIs listed under `parallel` go in one `batch([...])` call. Use the method exactly as catalogued (including unusual ones such as QUERY).
3. Write `k6/script.js`:
   - Target host only from `__ENV.BASE_URL`. No literal URLs. No credentials; secrets only via `__ENV`.
   - Support `smoke`, `baseline`, `load` (stepped ramp), `stress`, `spike` and `endurance`; create scenarios only for profiles marked needed in the BRD. `MAX_VUS` is bounded by the BRD cap and the environment cap.
   - Each needed profile's `parameters.flows` is a non-empty list of catalogue flow/transaction IDs. The runner passes these IDs in `__ENV.FLOWS`; filter the traffic mix so only selected flows execute. Smoke covers all active load-safe flows.
   - Build load and stress stages from the profile's BRD step parameters, a spike from base/spike/recovery parameters, and endurance from the agreed user count and duration. Read values from `__ENV`; do not invent defaults.
   - One function per transaction, each timing the whole transaction into the `transaction_duration` Trend, tagged `transaction: 'T1'`. Every request is tagged `transaction` and `api: '<catalogue id>'`.
   - Traffic mix weights = BRD traffic shares for the selected flows. Think time = BRD think time.
   - Values one call needs from another (ids, tokens) follow `dynamic_values` in the catalogue. If a transaction starts without them, collect them in `setup()` (untimed) and never time the setup calls.
   - Test data (search terms, ids) only from values in the catalogue or given by the user. Never real personal data.
   - Calls with `safe_to_load` of `no` or `conditional`, or deferred transactions, are not in the script.
4. Thresholds in `options.thresholds`:
   - One threshold per active requirement on `transaction_duration{transaction:Tx}` (response time, with the percentile and value from the BRD in milliseconds) or `http_req_failed` (error rate).
   - Abort conditions from the BRD as `{ threshold, abortOnFail: true, delayAbortEval }` entries: error rate, response time (for example 3x target), and `blocked_responses` (429, 503, CDN/WAF block) which aborts immediately.
   - Per-request metrics (`http_req_duration{api:...}`) are for diagnosis only; put no pass/fail thresholds on them.
5. Write `k6/requirement-map.yaml`: one entry per active requirement: `{requirement: PR-01, k6_metric: "transaction_duration{transaction:T2}", threshold: "p(95)<2000"}`. The strings must match the script exactly. The report step reads this file.
6. Run `python tools/k6check.py projects/<client>/<app>` and fix every issue. Repeat until it says OK.
7. Update `STATE.md` (stage "7. Script written", date). Tell the user to run the wrapper for all profiles; never invoke `k6 run` directly.

## Do not
- Do not run k6 or send any request in this step. Running is a separate step.
- Do not change `brd.yaml` or the catalogue to make the script fit. Report a mismatch to the user.
- Do not invent endpoints, fields, headers or test data.
- Do not remove the smoke profile, the VU cap or the abort thresholds.
