// SauceDemo is client-side only (no backend APIs for login, cart or checkout), so this script drives a real
// browser with the k6 browser module. Each iteration is one user journey T1 -> T2 -> T3 -> T4 (25% share each).
import { browser } from 'k6/browser';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

const BASE_URL = (__ENV.BASE_URL || '').replace(/\/$/, '');
if (!BASE_URL) {
  throw new Error('Set BASE_URL before running this script');
}
const USERNAME = __ENV.SAUCE_USERNAME;
const PASSWORD = __ENV.SAUCE_PASSWORD;

const PROFILE = __ENV.PROFILE || 'smoke';
const MAX_VUS = Math.min(5, Number(__ENV.MAX_VUS || 5));
const RAMP_UP = __ENV.RAMP_UP || '30s';
const STEADY = __ENV.STEADY || '3m';
const RAMP_DOWN = __ENV.RAMP_DOWN || '30s';
const THINK_SECONDS = 3;

// Synthetic checkout values given by the user for testing; not real personal data.
const CHECKOUT = { first: 'TestLead', last: 'JeeUser', postal: '68002600000' };

const blocked = new Counter('blocked_responses');
const txnFailed = new Rate('transaction_failed');
const txnDuration = new Trend('transaction_duration', true);

const browserOpts = { browser: { type: 'chromium' } };
const scenarios = PROFILE === 'smoke'
  ? { smoke: { executor: 'per-vu-iterations', vus: 1, iterations: 1, maxDuration: '2m', exec: 'journey', options: browserOpts } }
  : { load: { executor: 'ramping-vus', startVUs: 0, gracefulRampDown: '30s', exec: 'journey', options: browserOpts,
      stages: [{ duration: RAMP_UP, target: MAX_VUS }, { duration: STEADY, target: MAX_VUS }, { duration: RAMP_DOWN, target: 0 }] } };

export const options = {
  scenarios,
  thresholds: {
    'transaction_duration{transaction:T1}': ['p(95)<2000', { threshold: 'p(95)<10000', abortOnFail: true, delayAbortEval: '2m' }],
    'transaction_duration{transaction:T2}': ['p(95)<2000', { threshold: 'p(95)<10000', abortOnFail: true, delayAbortEval: '2m' }],
    'transaction_duration{transaction:T3}': ['p(95)<2000', { threshold: 'p(95)<10000', abortOnFail: true, delayAbortEval: '2m' }],
    'transaction_duration{transaction:T4}': ['p(95)<3000', { threshold: 'p(95)<10000', abortOnFail: true, delayAbortEval: '2m' }],
    transaction_failed: ['rate<0.01', { threshold: 'rate<0.05', abortOnFail: true, delayAbortEval: '2m' }],
    blocked_responses: [{ threshold: 'count<1', abortOnFail: true }],
  },
};

function guard(res) {
  if (res && (res.status() === 429 || res.status() === 503 || (res.headers() || {})['cf-mitigated'])) {
    blocked.add(1);
  }
}

// Times one transaction; the api tag links it to the catalogue entry the step was discovered on.
async function timed(tags, fn) {
  const { transaction } = tags;
  const t0 = Date.now();
  let ok = false;
  try {
    ok = await fn();
  } catch (e) {
    console.error(`${transaction} failed: ${e}`);
  }
  if (ok) txnDuration.add(Date.now() - t0, tags);
  txnFailed.add(!ok, tags);
  check(ok, { [`${transaction} completed`]: (v) => v === true }, { transaction });
  sleep(THINK_SECONDS);
  return ok;
}

async function t1(page) {
  return timed({ transaction: 'T1', api: 'API-001' }, async () => {
    const res = await page.goto(`${BASE_URL}/`, { waitUntil: 'load' });
    guard(res);
    await page.locator('#user-name').fill(USERNAME);
    await page.locator('#password').fill(PASSWORD);
    await page.locator('#login-button').click();
    await page.locator('.inventory_list').waitFor({ state: 'visible' });
    return page.url().includes('/inventory.html');
  });
}

async function t2(page) {
  return timed({ transaction: 'T2', api: 'API-002' }, async () => {
    await page.locator('.inventory_item_name').first().click();
    await page.locator('.inventory_details_name').waitFor({ state: 'visible' });
    await page.locator('#back-to-products').click();
    await page.locator('.inventory_list').waitFor({ state: 'visible' });
    return true;
  });
}

async function t3(page) {
  return timed({ transaction: 'T3', api: 'browser-only' }, async () => {
    await page.locator('.inventory_item button').first().click();
    await page.locator('.shopping_cart_badge').waitFor({ state: 'visible' });
    return (await page.locator('.shopping_cart_badge').textContent()) === '1';
  });
}

async function t4(page) {
  return timed({ transaction: 'T4', api: 'browser-only' }, async () => {
    await page.locator('.shopping_cart_link').click();
    await page.locator('#checkout').click();
    await page.locator('#first-name').fill(CHECKOUT.first);
    await page.locator('#last-name').fill(CHECKOUT.last);
    await page.locator('#postal-code').fill(CHECKOUT.postal);
    await page.locator('#continue').click();
    await page.locator('#finish').click();
    await page.locator('.complete-header').waitFor({ state: 'visible' });
    return page.url().includes('/checkout-complete.html');
  });
}

export async function journey() {
  if (!USERNAME || !PASSWORD) {
    throw new Error('Set SAUCE_USERNAME and SAUCE_PASSWORD in the environment before running');
  }
  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    if (!(await t1(page))) return;
    if (!(await t2(page))) return;
    if (!(await t3(page))) return;
    await t4(page);
  } finally {
    await page.close();
    await context.close();
  }
}
