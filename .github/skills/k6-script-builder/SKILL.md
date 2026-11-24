---
name: k6-script-builder
description: Generate a k6 performance script from brd.yaml and api-catalogue.yaml, with thresholds, abort rules and a requirement map for the report. Use for stage 5 (script) of the performance flow. Does not run the script.
---

# k6 script builder (stage 5)

Inputs: `projects/<client>/<app>/brd.yaml` and `api-catalogue.yaml`. Both checks must pass first:
`python tools/brd.py check <brd.yaml>` and `python tools/catalogue.py check <catalogue>`. If not, stop and tell the user.
Outputs: `projects/<client>/<app>/k6/script.js` and `k6/requirement-map.yaml`.

Start from `.github/skills/k6-script-builder/reference-skeleton.js` (tested). Keep its structure and guards; adapt CONFIG, MIX and the transaction functions.

## Procedure
1. Read the BRD: active transactions (those in `transactions`), traffic shares, think time, load profile (ramp-up, steady, ramp-down), peak users, requirements, abort conditions. Requirements whose notes say "deferred" are skipped.
2. Read the catalogue: for each active transaction, follow `flows` order. APIs listed under `parallel` go in one `batch([...])` call. Use the method exactly as catalogued (including unusual ones such as QUERY).
3. Write `k6/script.js`:
   - Target host only from `__ENV.BASE_URL`. No literal URLs. No credentials; secrets only via `__ENV`.
   - `PROFILE`: `smoke` (1 user, 1 pass over every transaction) and `load` (ramping profile from the BRD). `MAX_VUS` = `Math.min(<cap from BRD abort conditions>, env)`; the environment may only lower it.
   - One function per transaction, each timing the whole transaction into the `transaction_duration` Trend, tagged `transaction: 'T1'`. Every request is tagged `transaction` and `api: '<catalogue id>'`.
   - Traffic mix weights = BRD traffic shares. Think time = BRD think time.
   - Values one call needs from another (ids, tokens) follow `dynamic_values` in the catalogue. If a transaction starts without them, collect them in `setup()` (untimed) and never time the setup calls.
   - Never return a token, password or other secret from `setup()`: k6 writes setup data into `summary.json`, which would put it in the run files and make `clientpack.py` refuse. Keep tokens in a per-VU variable (a module-level `let` filled by an untimed login on the VU's first use).
   - Test data (search terms, ids) only from values in the catalogue or given by the user. Never real personal data.
   - Calls with `safe_to_load` of `no` or `conditional`, or deferred transactions, are not in the script.
   - Client-side apps (discovery found no backend API for login or other transactions, or pages return 404 without the browser session): only with the user's approval, drive the flow with the `k6/browser` module (`options: { browser: { type: 'chromium' } }` per scenario). Time each transaction into `transaction_duration`, record failures in a `transaction_failed` Rate (map the error-rate requirement to it), and read login names from the variables listed in `credentials_env_vars`. Never time an empty transaction.
4. Thresholds in `options.thresholds`:
   - Requirement and abort thresholds apply to the load profile only. The smoke profile gates on function only: `checks: ['rate==1']`, `http_req_failed: ['rate==0']` and `blocked_responses`. A slow but working system must still pass smoke; its speed is judged under load (see the skeleton's `PERF_THRESHOLDS`).
   - One threshold per active requirement on `transaction_duration{transaction:Tx}` (response time, with the percentile and value from the BRD in milliseconds) or `http_req_failed` (error rate).
   - Abort conditions from the BRD as `{ threshold, abortOnFail: true, delayAbortEval }` entries: error rate, response time (for example 3x target), and `blocked_responses` (429, 503, CDN/WAF block) which aborts immediately.
   - Per-request metrics (`http_req_duration{api:...}`) are for diagnosis only; put no pass/fail thresholds on them.
   - k6 exports a tagged sub-metric to `summary.json` only if a threshold names it, and the report reads them. So for every active transaction and every API in the script add an always-pass diagnostic entry: `transaction_duration{transaction:Tx}: ['max>=0']`, `http_req_duration{api:API-nnn}: ['max>=0']` and `http_reqs{api:API-nnn}: ['count>=0']`. Without them the report's per-transaction and per-API tables are empty.
5. Write `k6/requirement-map.yaml`: one entry per active requirement: `{requirement: PR-01, k6_metric: "transaction_duration{transaction:T2}", threshold: "p(95)<2000"}`. The strings must match the script exactly. The report step reads this file.
6. Run `python tools/k6check.py projects/<client>/<app>` and fix every issue. Repeat until it says OK.
7. Update `STATE.md` (stage "7. Script written", date). Tell the user how to run the first smoke test:
   `k6 run -e BASE_URL=<target> -e PROFILE=smoke projects/<client>/<app>/k6/script.js`

## Do not
- Do not run k6 or send any request in this step. Running is a separate step.
- Do not change `brd.yaml` or the catalogue to make the script fit. Report a mismatch to the user.
- Do not invent endpoints, fields, headers or test data.
- Do not remove the smoke profile, the VU cap or the abort thresholds.
