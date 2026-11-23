// Reference skeleton for generated k6 scripts. The agent adapts CONFIG, MIX and the transaction
// functions to the project's brd.yaml and api-catalogue.yaml. Keep the structure and the guards.
// No literal hosts, no credentials: everything environment-specific comes from __ENV.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Trend } from 'k6/metrics';

// ---------- CONFIG (from brd.yaml / api-catalogue.yaml) ----------
const BASE_URL = __ENV.BASE_URL;
if (!BASE_URL) { throw new Error('Set BASE_URL, for example: k6 run -e BASE_URL=<scheme>://<host> script.js'); }
const PROFILE = __ENV.PROFILE || 'smoke';                       // smoke | baseline | load | stress | spike | endurance
const MAX_VUS = Math.min(50, Number(__ENV.MAX_VUS || 50));      // hard cap from BRD abort conditions; env can only lower it
const FLOW_IDS = (__ENV.FLOWS || '').split(',').filter(Boolean);
const LOAD_STAGES = (__ENV.LOAD_STAGES || '').split(',').filter(Boolean).map((s) => {
  const [target, duration] = s.split(':');
  return { target: Number(target), duration };
});
const STRESS_STAGES = (__ENV.STRESS_STAGES || '').split(',').filter(Boolean).map((s) => {
  const [target, duration] = s.split(':');
  return { target: Number(target), duration };
});
const SPIKE_STAGES = (__ENV.SPIKE_STAGES || '').split(',').filter(Boolean).map((s) => {
  const [target, duration] = s.split(':');
  return { target: Number(target), duration };
});
const ENDURANCE_DURATION = __ENV.ENDURANCE_DURATION || '';
const RAMP_DOWN = `${__ENV.RAMP_DOWN || 0}s`;
const THINK_MIN = 1;                                            // seconds, from BRD think time
const THINK_MAX = 3;
const SEARCH_TERMS = ['term-a', 'term-b'];                      // only values observed in the catalogue / given by the user

// ---------- metrics ----------
const blocked = new Counter('blocked_responses');               // 429, 503 or CDN/WAF block
const txnDuration = new Trend('transaction_duration', true);    // wall time of a whole transaction

// ---------- options ----------
const rampScenario = (stages, startVUs = 0) => ({
  executor: 'ramping-vus', startVUs, gracefulRampDown: RAMP_DOWN, gracefulStop: '0s', exec: 'mixed', stages,
});
let scenarios;
if (PROFILE === 'smoke') {
  scenarios = { smoke: { executor: 'per-vu-iterations', vus: 1, iterations: 1, maxDuration: '2m', exec: 'smokeAll' } };
} else if (PROFILE === 'baseline') {
  scenarios = { baseline: { executor: 'per-vu-iterations', vus: MAX_VUS, iterations: 1, maxDuration: '2m', exec: 'smokeAll' } };
} else if (PROFILE === 'load') {
  scenarios = { load: rampScenario(LOAD_STAGES) };
} else if (PROFILE === 'stress') {
  scenarios = { stress: rampScenario(STRESS_STAGES, Number(__ENV.START_VUS || 0)) };
} else if (PROFILE === 'spike') {
  scenarios = { spike: rampScenario(SPIKE_STAGES, Number(__ENV.START_VUS || 0)) };
} else if (PROFILE === 'endurance') {
  scenarios = { endurance: { executor: 'constant-vus', vus: MAX_VUS, duration: ENDURANCE_DURATION, gracefulStop: RAMP_DOWN, exec: 'mixed' } };
} else {
  throw new Error(`Unsupported PROFILE: ${PROFILE}`);
}

export const options = {
  scenarios,
  thresholds: {
    // requirement thresholds (one line per active PR id; keep requirement-map.yaml in step with these)
    'transaction_duration{transaction:T2}': ['p(95)<2000', 'p(99)<4000', { threshold: 'p(95)<6000', abortOnFail: true, delayAbortEval: '2m' }],
    'transaction_duration{transaction:T1}': ['p(95)<2000', { threshold: 'p(95)<6000', abortOnFail: true, delayAbortEval: '2m' }],
    http_req_failed: ['rate<0.01', { threshold: 'rate<0.02', abortOnFail: true, delayAbortEval: '1m' }],
    // abort on any sign of throttling or blocking
    blocked_responses: [{ threshold: 'count<1', abortOnFail: true }],
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
function batch(reqs) {                                          // calls the browser fires in parallel
  const rs = http.batch(reqs.map((r) => [r.method, `${BASE_URL}${r.path}`, r.body ? JSON.stringify(r.body) : null, { headers: HEADERS, tags: r.tags }]));
  rs.forEach((res, i) => { guard(res); check(res, { 'status is 2xx': (x) => x.status >= 200 && x.status < 300 }, reqs[i].tags); });
  return rs;
}
function think() { sleep(THINK_MIN + Math.random() * (THINK_MAX - THINK_MIN)); }
function pickOne(list) { return list[Math.floor(Math.random() * list.length)]; }

// ---------- transactions (one function per BRD transaction; tags: transaction + api id) ----------
function t1() {                                                 // parallel page-load calls
  const t0 = Date.now();
  batch([
    { method: 'GET', path: '/categories', tags: { transaction: 'T1', api: 'API-001' } },
    { method: 'GET', path: '/brands', tags: { transaction: 'T1', api: 'API-002' } },
    { method: 'QUERY', path: '/items', body: { page: '1' }, tags: { transaction: 'T1', api: 'API-003' } },
  ]);
  txnDuration.add(Date.now() - t0, { transaction: 'T1' });
  think();
}
function t2() {
  const t0 = Date.now();
  call('QUERY', '/items/search', { q: pickOne(SEARCH_TERMS) }, { transaction: 'T2', api: 'API-004' });
  txnDuration.add(Date.now() - t0, { transaction: 'T2' });
  think();
}
function t3(data) {                                             // id comes from setup(), not timed
  const id = pickOne(data.ids);
  const t0 = Date.now();
  call('GET', `/items/${id}`, null, { transaction: 'T3', api: 'API-005' });
  call('GET', `/items/${id}/related`, null, { transaction: 'T3', api: 'API-006' });
  txnDuration.add(Date.now() - t0, { transaction: 'T3' });
  think();
}

// ---------- traffic mix (weights from BRD traffic share) ----------
const MIX = [{ id: 'T1', weight: 44, run: t1 }, { id: 'T2', weight: 31, run: t2 }, { id: 'T3', weight: 25, run: t3 }];
const ACTIVE_MIX = FLOW_IDS.length ? MIX.filter((t) => FLOW_IDS.includes(t.id)) : MIX;
const TOTAL = ACTIVE_MIX.reduce((s, t) => s + t.weight, 0);
if (!ACTIVE_MIX.length) { throw new Error('FLOWS must select at least one BRD flow'); }
function pick() { let r = Math.random() * TOTAL; for (const t of ACTIVE_MIX) { r -= t.weight; if (r < 0) return t; } return ACTIVE_MIX[ACTIVE_MIX.length - 1]; }

// ---------- lifecycle ----------
export function setup() {                                       // untimed: collect ids needed by later transactions
  const res = http.request('QUERY', `${BASE_URL}/items`, JSON.stringify({ page: '1' }), { headers: HEADERS, tags: { phase: 'setup' } });
  guard(res);
  const ids = res.status === 200 ? (res.json('data') || []).map((p) => p.id) : [];
  if (!ids.length) { throw new Error(`setup failed: no ids found (status ${res.status})`); }
  return { ids };
}
export function mixed(data) { pick().run(data); }
export function smokeAll(data) { ACTIVE_MIX.forEach((t) => t.run(data)); }
