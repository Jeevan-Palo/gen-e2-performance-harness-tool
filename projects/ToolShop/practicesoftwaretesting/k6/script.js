// k6 script generated from brd.yaml and api-catalogue.yaml (Step 7). Do not run from this step.
// Active transactions: T1 (Browse product catalogue), T2 (Search products by keyword), T3 (View product details).
// T4 (Add item to cart) and T5 (Checkout and place order) are in brd.yaml scope_out - not discovered, deferred to a
// later phase - and are intentionally NOT implemented here (requirements PR-03, PR-04, PR-07 are deferred).
// No literal hosts, no credentials: everything environment-specific comes from __ENV.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Trend } from 'k6/metrics';

// ---------- CONFIG (from brd.yaml / api-catalogue.yaml) ----------
const BASE_URL = __ENV.BASE_URL;
if (!BASE_URL) { throw new Error('Set BASE_URL, for example: k6 run -e BASE_URL=<scheme>://<host> script.js'); }
const PROFILE = __ENV.PROFILE || 'smoke';                       // smoke = 1 user, 1 pass | load = ramping profile
const MAX_VUS = Math.min(50, Number(__ENV.MAX_VUS || 50));      // BRD risk: "never more than 50 virtual users"; env can only lower it
const RAMP_UP = __ENV.RAMP_UP || '2m';                          // brd.yaml workload.peak_window
const STEADY = __ENV.STEADY || '10m';
const RAMP_DOWN = __ENV.RAMP_DOWN || '3m';
const THINK_MIN = 1;                                            // seconds, brd.yaml workload.think_time (random 1-3s)
const THINK_MAX = 3;
// Catalogue API-005 test_data/evidence records only 'Hammer' as an observed search term; add more here only after
// recording them in api-catalogue.yaml's API-005 test_data, not invented.
const SEARCH_TERMS = ['Hammer'];

// ---------- metrics ----------
const blocked = new Counter('blocked_responses');               // BRD abort condition "Server health": 429, 503 or CDN/firewall block
const txnDuration = new Trend('transaction_duration', true);    // wall time of a whole transaction

// ---------- options ----------
const scenarios = PROFILE === 'smoke'
  ? { smoke: { executor: 'per-vu-iterations', vus: 1, iterations: 1, maxDuration: '2m', exec: 'smokeAll' } }
  : { load: { executor: 'ramping-vus', startVUs: 0, gracefulRampDown: '30s', exec: 'mixed',
              stages: [{ duration: RAMP_UP, target: MAX_VUS }, { duration: STEADY, target: MAX_VUS }, { duration: RAMP_DOWN, target: 0 }] } };

export const options = {
  scenarios,
  thresholds: {
    // PR-01 (Must), PR-02 (Must): T2 search response time. 3x-target entry = BRD abort condition "Response time".
    'transaction_duration{transaction:T2}': ['p(95)<2000', 'p(99)<4000', { threshold: 'p(95)<6000', abortOnFail: true, delayAbortEval: '2m' }],
    // PR-06 (Should): T1 and T3 response time, split per transaction (k6 tags are matched per value).
    'transaction_duration{transaction:T1}': ['p(95)<2000', { threshold: 'p(95)<6000', abortOnFail: true, delayAbortEval: '2m' }],
    'transaction_duration{transaction:T3}': ['p(95)<2000', { threshold: 'p(95)<6000', abortOnFail: true, delayAbortEval: '2m' }],
    // PR-05 (Must): error rate, all transactions. 2% entry = BRD abort condition "Error rate".
    http_req_failed: ['rate<0.01', { threshold: 'rate<0.02', abortOnFail: true, delayAbortEval: '1m' }],
    // BRD abort condition "Server health": abort immediately on any 429/503/CDN block.
    blocked_responses: [{ threshold: 'count<1', abortOnFail: true }],
    // BRD abort conditions "Impact on other systems/users" and "Request from operations/environment owner" are
    // procedural (require human judgement), not machine-checkable; they are not represented as k6 thresholds.
  },
};

// ---------- helpers ----------
const HEADERS = { 'Content-Type': 'application/json', Accept: 'application/json' };
function guard(res) { if (res.status === 429 || res.status === 503 || res.headers['Cf-Mitigated']) { blocked.add(1); } }
function call(method, path, body, tags) {
  const res = http.request(method, `${BASE_URL}${path}`, body ? JSON.stringify(body) : null, { headers: HEADERS, tags });
  guard(res);
  check(res, { 'status is 2xx': (r) => r.status >= 200 && r.status < 300 }, tags);
  return res;
}
function batch(reqs) {                                          // calls the browser fires in parallel (api-catalogue.yaml flows[T1].parallel)
  const rs = http.batch(reqs.map((r) => [r.method, `${BASE_URL}${r.path}`, r.body ? JSON.stringify(r.body) : null, { headers: HEADERS, tags: r.tags }]));
  rs.forEach((res, i) => { guard(res); check(res, { 'status is 2xx': (x) => x.status >= 200 && x.status < 300 }, reqs[i].tags); });
  return rs;
}
function think() { sleep(THINK_MIN + Math.random() * (THINK_MAX - THINK_MIN)); }
function pickOne(list) { return list[Math.floor(Math.random() * list.length)]; }

// ---------- transactions (one function per BRD transaction; tags: transaction + api id) ----------
function t1() {                                                 // T1: Browse product catalogue - API-001..API-004, all parallel on page load
  const t0 = Date.now();
  batch([
    { method: 'GET', path: '/categories/tree', tags: { transaction: 'T1', api: 'API-001' } },
    { method: 'GET', path: '/product-specs/names', tags: { transaction: 'T1', api: 'API-002' } },
    { method: 'GET', path: '/brands', tags: { transaction: 'T1', api: 'API-003' } },
    { method: 'QUERY', path: '/products', body: { page: '1', between: 'price,1,100', is_rental: 'false' }, tags: { transaction: 'T1', api: 'API-004' } },
  ]);
  txnDuration.add(Date.now() - t0, { transaction: 'T1' });
  think();
}
function t2() {                                                 // T2: Search products by keyword - API-005
  const t0 = Date.now();
  call('QUERY', '/products/search', { q: pickOne(SEARCH_TERMS) }, { transaction: 'T2', api: 'API-005' });
  txnDuration.add(Date.now() - t0, { transaction: 'T2' });
  think();
}
function t3(data) {                                             // T3: View product details - API-006, API-007; id comes from setup(), not timed
  const id = pickOne(data.productIds);
  const t0 = Date.now();
  call('GET', `/products/${id}`, null, { transaction: 'T3', api: 'API-006' });
  call('GET', `/products/${id}/related`, null, { transaction: 'T3', api: 'API-007' });
  txnDuration.add(Date.now() - t0, { transaction: 'T3' });
  think();
}

// ---------- traffic mix (weights from brd.yaml transactions traffic_share: T1 44%, T2 31%, T3 25%) ----------
const MIX = [{ id: 'T1', weight: 44, run: t1 }, { id: 'T2', weight: 31, run: t2 }, { id: 'T3', weight: 25, run: t3 }];
const TOTAL = MIX.reduce((s, t) => s + t.weight, 0);
function pick() { let r = Math.random() * TOTAL; for (const t of MIX) { r -= t.weight; if (r < 0) return t; } return MIX[MIX.length - 1]; }

// ---------- lifecycle ----------
export function setup() {                                       // untimed: collect product ids needed by T3 (dynamic_values: API-004 -> API-006/API-007)
  const res = http.request('QUERY', `${BASE_URL}/products`, JSON.stringify({ page: '1', between: 'price,1,100', is_rental: 'false' }), { headers: HEADERS, tags: { phase: 'setup' } });
  guard(res);
  const productIds = res.status === 200 ? (res.json('data') || []).map((p) => p.id) : [];
  if (!productIds.length) { throw new Error(`setup failed: no product ids found (status ${res.status})`); }
  return { productIds };
}
export function mixed(data) { pick().run(data); }
export function smokeAll(data) { MIX.forEach((t) => t.run(data)); }
