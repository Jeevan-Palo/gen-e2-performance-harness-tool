// Generated from brd.yaml and api-catalogue.yaml (OrangeHRM). Host from __ENV.BASE_URL; credentials only from __ENV.
// One journey per iteration (T1 -> T2 -> T3 -> T4), matching the BRD's equal 25% traffic shares;
// k6 resets cookies each iteration, so every journey starts with a fresh login.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

// ---------- CONFIG ----------
const BASE_URL = __ENV.BASE_URL;
if (!BASE_URL) { throw new Error('Set BASE_URL, for example: k6 run -e BASE_URL=<scheme>://<host> script.js'); }
const USERNAME = __ENV.ORANGEHRM_USERNAME;
const PASSWORD = __ENV.ORANGEHRM_PASSWORD;
const PROFILE = __ENV.PROFILE || 'smoke';
const MAX_VUS = Math.min(5, Number(__ENV.MAX_VUS || 5));        // cap from environment limit (BRD peak: up to 5 users)
const RAMP_UP = __ENV.RAMP_UP || '5m';
const STEADY = __ENV.STEADY || '20m';
const RAMP_DOWN = __ENV.RAMP_DOWN || '5m';
const THINK_S = 5;                                              // BRD think time: 5 s between user actions
const SEARCH_TERMS = ['a'];                                     // term used in discovery (catalogue API-017/018)
const W = '/web/index.php';

// ---------- metrics ----------
const blocked = new Counter('blocked_responses');
const txnDuration = new Trend('transaction_duration', true);
const txnFailed = new Rate('transaction_failed');

// ---------- options ----------
const scenarios = PROFILE === 'smoke'
  ? { smoke: { executor: 'per-vu-iterations', vus: 1, iterations: 1, maxDuration: '2m', exec: 'smokeAll' } }
  : { load: { executor: 'ramping-vus', startVUs: 0, gracefulRampDown: '30s', exec: 'mixed',
              stages: [{ duration: RAMP_UP, target: MAX_VUS }, { duration: STEADY, target: MAX_VUS }, { duration: RAMP_DOWN, target: 0 }] } };

// Smoke proves the script works; response-time targets are judged only under load.
const PERF_THRESHOLDS = PROFILE === 'smoke' ? { checks: ['rate==1'], http_req_failed: ['rate==0'], transaction_failed: ['rate==0'] } : {
  'transaction_duration{transaction:T1}': ['p(95)<3000', { threshold: 'p(95)<10000', abortOnFail: true, delayAbortEval: '2m' }],
  'transaction_duration{transaction:T2}': ['p(95)<3000', { threshold: 'p(95)<10000', abortOnFail: true, delayAbortEval: '2m' }],
  'transaction_duration{transaction:T3}': ['p(95)<3000', { threshold: 'p(95)<10000', abortOnFail: true, delayAbortEval: '2m' }],
  'transaction_duration{transaction:T4}': ['p(95)<3000', { threshold: 'p(95)<10000', abortOnFail: true, delayAbortEval: '2m' }],
  http_req_failed: ['rate<0.01', { threshold: 'rate<0.05', abortOnFail: true, delayAbortEval: '2m' }],
  transaction_failed: ['rate<0.01'],
};

export const options = {
  scenarios,
  thresholds: {
    ...PERF_THRESHOLDS,
    blocked_responses: [{ threshold: 'count<1', abortOnFail: true }],
  },
};

// ---------- helpers ----------
const JSON_HEADERS = { Accept: 'application/json' };
function guard(res) { if (res.status === 429 || res.status === 503 || res.headers['Cf-Mitigated']) { blocked.add(1); } }
function ok(res, tags) { guard(res); return check(res, { 'status is 2xx': (r) => r.status >= 200 && r.status < 300 }, tags); }
function get(path, tags, headers) { const res = http.get(`${BASE_URL}${W}${path}`, { headers: headers || {}, tags }); return ok(res, tags) ? res : null; }
function batch(tx, reqs) {
  const rs = http.batch(reqs.map((r) => ['GET', `${BASE_URL}${W}${r.path}`, null, { headers: JSON_HEADERS, tags: r.tags }]));
  return rs.every((res, i) => ok(res, reqs[i].tags));
}
function timed(tx, fn) {
  const t0 = Date.now();
  let passed = false;
  try { passed = fn() === true; } catch (e) { passed = false; }
  txnDuration.add(Date.now() - t0, { transaction: tx });
  txnFailed.add(!passed, { transaction: tx });
  sleep(THINK_S);
  return passed;
}
function pickOne(list) { return list[Math.floor(Math.random() * list.length)]; }
function today() { return new Date().toISOString().slice(0, 10); }
function q(s) { return s.replace(/ /g, '%20'); }

// ---------- transactions ----------
function t1() {
  return timed('T1', () => {
    const page = get('/auth/login', { transaction: 'T1', api: 'API-001' });
    const m = page && /:token="&quot;([^&]+)&quot;"/.exec(page.body);
    if (!m) { return false; }
    const login = http.post(`${BASE_URL}${W}/auth/validate`, { _token: m[1], username: USERNAME, password: PASSWORD },
      { tags: { transaction: 'T1', api: 'API-002' } });
    guard(login);
    // the redirect lands on API-003 (dashboard); a failed login lands back on the login page
    if (!check(login, { 'logged in': (r) => r.status === 200 && r.url.includes('/dashboard/index') }, { transaction: 'T1', api: 'API-003' })) { return false; }
    const now = new Date();
    const hhmm = `${String(now.getUTCHours()).padStart(2, '0')}:${String(now.getUTCMinutes()).padStart(2, '0')}`;
    return batch('T1', [
      { path: `/api/v2/dashboard/employees/time-at-work?timezoneOffset=0&currentDate=${today()}&currentTime=${hhmm}`, tags: { transaction: 'T1', api: 'API-004' } },
      { path: '/api/v2/dashboard/shortcuts', tags: { transaction: 'T1', api: 'API-005' } },
      { path: '/api/v2/dashboard/employees/action-summary', tags: { transaction: 'T1', api: 'API-006' } },
      { path: '/api/v2/buzz/feed?limit=5&offset=0&sortOrder=DESC&sortField=share.createdAtUtc', tags: { transaction: 'T1', api: 'API-007' } },
      { path: `/api/v2/dashboard/employees/leaves?date=${today()}`, tags: { transaction: 'T1', api: 'API-008' } },
      { path: '/api/v2/dashboard/employees/subunit', tags: { transaction: 'T1', api: 'API-009' } },
      { path: '/api/v2/dashboard/employees/locations', tags: { transaction: 'T1', api: 'API-010' } },
    ]);
  });
}
function t2() {
  return timed('T2', () => {
    if (!get('/pim/viewEmployeeList', { transaction: 'T2', api: 'API-012' })) { return false; }
    return batch('T2', [
      { path: '/api/v2/pim/employees?limit=50&offset=0&model=detailed&includeEmployees=onlyCurrent&sortField=employee.firstName&sortOrder=ASC', tags: { transaction: 'T2', api: 'API-013' } },
      { path: '/api/v2/admin/employment-statuses?limit=0', tags: { transaction: 'T2', api: 'API-014' } },
      { path: '/api/v2/admin/job-titles?limit=0', tags: { transaction: 'T2', api: 'API-015' } },
      { path: '/api/v2/admin/subunits', tags: { transaction: 'T2', api: 'API-016' } },
    ]);
  });
}
function t3() {
  const term = q(pickOne(SEARCH_TERMS));
  return timed('T3', () => {
    if (!get(`/api/v2/pim/employees?nameOrId=${term}&includeEmployees=onlyCurrent`, { transaction: 'T3', api: 'API-017' }, JSON_HEADERS)) { return false; }
    return get(`/api/v2/pim/employees?limit=50&offset=0&model=detailed&nameOrId=${term}&includeEmployees=onlyCurrent&sortField=employee.firstName&sortOrder=ASC`,
      { transaction: 'T3', api: 'API-018' }, JSON_HEADERS) !== null;
  });
}
function t4() {
  const year = today().slice(0, 4);
  return timed('T4', () => {
    if (!get('/leave/viewLeaveList', { transaction: 'T4', api: 'API-019' })) { return false; }
    return batch('T4', [
      { path: '/api/v2/leave/employees/leave-requests?limit=50&offset=0&includeEmployees=onlyCurrent', tags: { transaction: 'T4', api: 'API-020' } },
      { path: '/api/v2/leave/leave-periods', tags: { transaction: 'T4', api: 'API-021' } },
      { path: '/api/v2/leave/workweek?model=indexed', tags: { transaction: 'T4', api: 'API-022' } },
      { path: '/api/v2/leave/leave-types?limit=0', tags: { transaction: 'T4', api: 'API-023' } },
      { path: `/api/v2/leave/holidays?fromDate=${year}-01-01&toDate=${year}-12-31`, tags: { transaction: 'T4', api: 'API-024' } },
    ]);
  });
}

// ---------- traffic mix (BRD: 25% each, as one journey) ----------
const MIX = [{ id: 'T1', weight: 25, run: t1 }, { id: 'T2', weight: 25, run: t2 }, { id: 'T3', weight: 25, run: t3 }, { id: 'T4', weight: 25, run: t4 }];

// ---------- lifecycle ----------
export function setup() { if (!USERNAME || !PASSWORD) { throw new Error('Set ORANGEHRM_USERNAME and ORANGEHRM_PASSWORD in the environment'); } }
function journey() { if (!MIX[0].run()) { return; } MIX.slice(1).forEach((t) => t.run()); }
export function mixed() { journey(); }
export function smokeAll() { journey(); }
