// k6 script generated from brd.yaml and api-catalogue.yaml (saucedemo / postmancollection).
// No literal hosts, no credentials: the host and the test account come from __ENV.
//   k6 run -e BASE_URL=<scheme>://<host> -e APP_USER=<user> -e APP_PASSWORD=<password> -e PROFILE=smoke script.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Trend } from 'k6/metrics';

// ---------- CONFIG (from brd.yaml / api-catalogue.yaml / environments.yaml) ----------
const BASE_URL = __ENV.BASE_URL;
if (!BASE_URL) { throw new Error('Set BASE_URL, for example: k6 run -e BASE_URL=<scheme>://<host> script.js'); }
const APP_USER = __ENV.APP_USER;
const APP_PASSWORD = __ENV.APP_PASSWORD;
const PROFILE = __ENV.PROFILE || 'smoke';                       // smoke = 1 user, 1 pass | load = ramping profile
const MAX_VUS = Math.min(5, Number(__ENV.MAX_VUS || 5));        // environment limit is 5 users; the run can only lower it
const RAMP_UP = __ENV.RAMP_UP || '30s';
const STEADY = __ENV.STEADY || '2m';
const RAMP_DOWN = __ENV.RAMP_DOWN || '30s';
const THINK_SECONDS = 5;                                        // BRD think time: 5 seconds between user actions
const SEARCH_TERM = 'phone';                                    // from the collection (API-004)
const ITEM_ID = 1;                                              // product and cart id from the collection URLs (API-003, API-005, API-007, API-008)

// ---------- metrics ----------
const blocked = new Counter('blocked_responses');               // 429, 503 or CDN/WAF block
const txnDuration = new Trend('transaction_duration', true);    // wall time of a whole transaction

// ---------- options ----------
const scenarios = PROFILE === 'smoke'
  ? { smoke: { executor: 'per-vu-iterations', vus: 1, iterations: 1, maxDuration: '2m', exec: 'smokeAll' } }
  : { load: { executor: 'ramping-vus', startVUs: 0, gracefulRampDown: '30s', exec: 'mixed',
              stages: [{ duration: RAMP_UP, target: MAX_VUS }, { duration: STEADY, target: MAX_VUS }, { duration: RAMP_DOWN, target: 0 }] } };

// Smoke proves the script works (every check passes, no errors, no blocks); targets are judged only under load.
const PERF_THRESHOLDS = PROFILE === 'smoke' ? { checks: ['rate==1'], http_req_failed: ['rate==0'] } : {
  // PR-01 error rate <= 1%; abort: error rate > 5% for 2 minutes
  http_req_failed: ['rate<0.01', { threshold: 'rate<0.05', abortOnFail: true, delayAbortEval: '2m' }],
  // abort: p95 > 10 s for 2 minutes
  transaction_duration: [{ threshold: 'p(95)<10000', abortOnFail: true, delayAbortEval: '2m' }],
};

// Diagnostic only: k6 exports a tagged sub-metric to the summary only if a threshold names it. These can never fail;
// they make the report show timings per transaction and per API.
const DIAGNOSTIC = {};
['T1', 'T2', 'T3'].forEach((x) => { DIAGNOSTIC[`transaction_duration{transaction:${x}}`] = ['max>=0']; });
['API-001', 'API-002', 'API-003', 'API-004', 'API-005', 'API-006', 'API-007', 'API-008'].forEach((x) => {
  DIAGNOSTIC[`http_req_duration{api:${x}}`] = ['max>=0'];
  DIAGNOSTIC[`http_reqs{api:${x}}`] = ['count>=0'];
});

export const options = {
  scenarios,
  thresholds: {
    ...DIAGNOSTIC,
    ...PERF_THRESHOLDS,
    // abort on any sign of throttling or blocking (both profiles)
    blocked_responses: [{ threshold: 'count<1', abortOnFail: true }],
  },
};

// ---------- helpers ----------
function headers(token) {
  const h = { 'Content-Type': 'application/json', Accept: 'application/json' };
  if (token) { h.Authorization = `Bearer ${token}`; }
  return h;
}
function guard(res) { if (res.status === 429 || res.status === 503 || res.headers['Cf-Mitigated']) { blocked.add(1); } }
function call(method, path, body, tags, token) {
  const res = http.request(method, `${BASE_URL}${path}`, body ? JSON.stringify(body) : null, { headers: headers(token), tags });
  guard(res);
  check(res, { 'status is 2xx': (r) => r.status >= 200 && r.status < 300 }, tags);
  return res;
}
function think() { sleep(THINK_SECONDS); }

// Each VU logs in once, untimed, and keeps the token in memory. It is deliberately not returned from setup():
// k6 writes setup data into the summary export, which would put the token into the run files.
let vuToken = null;
function token() {
  if (vuToken) { return vuToken; }
  if (!APP_USER || !APP_PASSWORD) { throw new Error('Set APP_USER and APP_PASSWORD (the test account) in the environment'); }
  const res = http.request('POST', `${BASE_URL}/auth/login`, JSON.stringify({ username: APP_USER, password: APP_PASSWORD }), { headers: headers(), tags: { phase: 'vu-login' } });
  guard(res);
  vuToken = res.status === 200 ? res.json('accessToken') : null;
  if (!vuToken) { throw new Error(`login did not return a token (status ${res.status})`); }
  return vuToken;
}

// ---------- transactions (one function per BRD transaction; tags: transaction + api id) ----------
function t1() {                                                 // Authentication: API-001
  const t0 = Date.now();
  const res = call('POST', '/auth/login', { username: APP_USER, password: APP_PASSWORD }, { transaction: 'T1', api: 'API-001' });
  check(res, { 'login returns accessToken': (r) => r.status === 200 && !!r.json('accessToken') }, { transaction: 'T1', api: 'API-001' });
  txnDuration.add(Date.now() - t0, { transaction: 'T1' });
  think();
}
function t2() {                                                 // Inventory: API-002, API-003, API-004 (token from the VU's untimed login)
  const tk = token();
  const t0 = Date.now();
  call('GET', '/products', null, { transaction: 'T2', api: 'API-002' }, tk);
  call('GET', `/products/${ITEM_ID}`, null, { transaction: 'T2', api: 'API-003' }, tk);
  call('GET', `/products/search?q=${SEARCH_TERM}`, null, { transaction: 'T2', api: 'API-004' }, tk);
  txnDuration.add(Date.now() - t0, { transaction: 'T2' });
  think();
}
function t3() {                                                 // Cart: API-005, API-006, API-007, API-008
  const tk = token();
  const t0 = Date.now();
  call('GET', `/carts/${ITEM_ID}`, null, { transaction: 'T3', api: 'API-005' }, tk);
  call('POST', '/carts/add', { userId: 1, products: [{ id: 1, quantity: 1 }] }, { transaction: 'T3', api: 'API-006' }, tk);
  call('PUT', `/carts/${ITEM_ID}`, { merge: false, products: [{ id: 1, quantity: 3 }] }, { transaction: 'T3', api: 'API-007' }, tk);
  call('DELETE', `/carts/${ITEM_ID}`, null, { transaction: 'T3', api: 'API-008' }, tk);
  txnDuration.add(Date.now() - t0, { transaction: 'T3' });
  think();
}

// ---------- traffic mix (weights from BRD traffic share) ----------
const MIX = [{ id: 'T1', weight: 34, run: t1 }, { id: 'T2', weight: 33, run: t2 }, { id: 'T3', weight: 33, run: t3 }];
const TOTAL = MIX.reduce((s, t) => s + t.weight, 0);
function pick() { let r = Math.random() * TOTAL; for (const t of MIX) { r -= t.weight; if (r < 0) return t; } return MIX[MIX.length - 1]; }

// ---------- lifecycle ----------
export function mixed() { pick().run(); }
export function smokeAll() { MIX.forEach((t) => t.run()); }
