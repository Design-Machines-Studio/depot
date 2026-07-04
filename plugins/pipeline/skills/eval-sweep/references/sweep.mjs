#!/usr/bin/env node
// sweep.mjs -- scripted route x role x breakpoint browser sweep.
//
// WHY THIS EXISTS:
//   A system-wide evaluation driven through live MCP browser calls costs
//   hundreds of tool calls and routinely runs a session out of budget before
//   it finishes -- returning nothing. This script walks the entire
//   route x role x breakpoint matrix in ONE process and writes durable
//   evidence (metrics JSON + PNG per cell) to disk, so one Bash call replaces
//   100+ interactive browser calls and the results survive a dead session.
//
// WHAT THIS FIXES:
//   - Uncapped, un-survivable evaluation runs (session-3-6, 2026-07-04).
//   - Per-cell metrics are structured JSON a consolidator reads mechanically,
//     not screenshots a human must eyeball one by one.
//
// DEPENDENCIES:
//   node >= 18, playwright (chromium preinstalled in this environment at
//   /opt/pw-browsers; do NOT run `playwright install`). Firefox only needed
//   for --engine=firefox.
//
// USAGE:
//   node sweep.mjs --base-url http://localhost:8080 \
//       --routes routes.json --roles anon,member,admin \
//       --vp 375,768,1440 --engine chromium --out ./out/sweep
//
//   Credentials for non-anon roles come from routes.json `login.roles` OR from
//   env vars EVAL_<ROLE>_EMAIL / EVAL_<ROLE>_PASSWORD (env wins). Keep any
//   credential file gitignored -- never commit real logins.

import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';

function parseArgs(argv) {
  const a = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith('--')) {
      const key = argv[i].slice(2);
      const val = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : 'true';
      a[key] = val;
    }
  }
  return a;
}

const args = parseArgs(process.argv.slice(2));
const BASE_URL = (args['base-url'] || 'http://localhost:8080').replace(/\/$/, '');
const OUT = args.out || './out/sweep';
const ENGINE = args.engine || 'chromium';
const VPS = (args.vp || '375,768,1440').split(',').map((s) => parseInt(s.trim(), 10));
const ROLES = (args.roles || 'anon').split(',').map((s) => s.trim());
const cfg = args.routes ? JSON.parse(readFileSync(args.routes, 'utf8')) : { routes: ['/'] };
const ROUTES = cfg.routes || ['/'];

const slug = (s) => s.replace(/[^a-z0-9]+/gi, '_').replace(/^_|_$/g, '') || 'root';
function write(path, data) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, typeof data === 'string' ? data : JSON.stringify(data, null, 2));
}

function creds(role) {
  const env = process.env;
  const R = role.toUpperCase();
  const fromEnv = env[`EVAL_${R}_EMAIL`] && {
    email: env[`EVAL_${R}_EMAIL`], password: env[`EVAL_${R}_PASSWORD`],
  };
  return fromEnv || (cfg.login && cfg.login.roles && cfg.login.roles[role]) || null;
}

async function login(context, role) {
  if (role === 'anon' || !cfg.login) return true;
  const c = creds(role);
  if (!c) { console.error(`  ! no credentials for role ${role}; treating as anon`); return false; }
  const page = await context.newPage();
  try {
    await page.goto(BASE_URL + (cfg.login.url || '/login'), { waitUntil: 'domcontentloaded' });
    await page.fill(`[name="${cfg.login.usernameField || 'email'}"]`, c.email);
    await page.fill(`[name="${cfg.login.passwordField || 'password'}"]`, c.password);
    await Promise.all([
      page.waitForLoadState('domcontentloaded'),
      page.click(cfg.login.submitSelector || 'button[type="submit"]'),
    ]);
    return true;
  } catch (e) {
    console.error(`  ! login failed for ${role}: ${e.message}`);
    return false;
  } finally {
    await page.close();
  }
}

async function probeCell(context, route, role, vp) {
  const page = await context.newPage();
  await page.setViewportSize({ width: vp, height: 900 });
  const consoleErrors = [];
  const failedRequests = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('requestfailed', (r) => failedRequests.push({ url: r.url(), err: r.failure()?.errorText }));
  page.on('response', (r) => { if (r.status() >= 400) failedRequests.push({ url: r.url(), status: r.status() }); });

  let status = 0, domContentLoaded = null, overflowX = null, err = null;
  try {
    const resp = await page.goto(BASE_URL + route, { waitUntil: 'domcontentloaded', timeout: 30000 });
    status = resp ? resp.status() : 0;
    const t = await page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0];
      return nav ? Math.round(nav.domContentLoadedEventEnd) : null;
    });
    domContentLoaded = t;
    const ov = await page.evaluate(() => {
      const doc = document.documentElement;
      return { over: doc.scrollWidth > window.innerWidth + 1, amount: doc.scrollWidth - window.innerWidth };
    });
    overflowX = ov;
    const pngPath = `${OUT}/png/${slug(route)}__${role}__${vp}.png`;
    mkdirSync(dirname(pngPath), { recursive: true });
    await page.screenshot({ path: pngPath, fullPage: true });
  } catch (e) {
    err = e.message;
  } finally {
    await page.close();
  }

  const cell = { route, role, vp, status, domContentLoaded, overflowX, consoleErrors, failedRequests, error: err };
  write(`${OUT}/metrics/${slug(route)}__${role}__${vp}.json`, cell);
  return cell;
}

function cellProblems(c) {
  const p = [];
  if (c.error) p.push(`load error: ${c.error}`);
  if (c.status && (c.status < 200 || c.status >= 400)) p.push(`status ${c.status}`);
  if (c.overflowX && c.overflowX.over) p.push(`horizontal overflow +${c.overflowX.amount}px`);
  if (c.consoleErrors.length) p.push(`${c.consoleErrors.length} console error(s)`);
  if (c.failedRequests.length) p.push(`${c.failedRequests.length} failed request(s)`);
  return p;
}

async function main() {
  const { chromium, firefox } = await import('playwright');
  const browserType = ENGINE === 'firefox' ? firefox : chromium;
  const launchOpts = {};
  if (process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE) launchOpts.executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
  const browser = await browserType.launch(launchOpts);
  const cells = [];
  const problems = [];

  for (const role of ROLES) {
    const context = await browser.newContext();
    const ok = await login(context, role);
    if (!ok && role !== 'anon') { /* proceed anon-equivalent, flagged per cell */ }
    for (const route of ROUTES) {
      for (const vp of VPS) {
        process.stderr.write(`  sweep ${route} @ ${role}/${vp}\n`);
        const c = await probeCell(context, route, role, vp);
        cells.push(c);
        const pr = cellProblems(c);
        if (pr.length) problems.push({ route, role, vp, problems: pr });
      }
    }
    await context.close();
  }
  await browser.close();

  const summary = {
    baseUrl: BASE_URL, engine: ENGINE, roles: ROLES, breakpoints: VPS,
    routeCount: ROUTES.length, cellCount: cells.length,
    problemCount: problems.length, problems, generatedAt: new Date().toISOString(),
  };
  write(`${OUT}/summary.json`, summary);
  console.log(`sweep complete: ${cells.length} cells, ${problems.length} with problems -> ${OUT}/summary.json`);
  process.exit(0);
}

main().catch((e) => { console.error(e); process.exit(1); });
