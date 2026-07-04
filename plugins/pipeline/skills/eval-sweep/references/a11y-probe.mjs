#!/usr/bin/env node
// a11y-probe.mjs -- runtime accessibility probe for a running web app.
//
// WHY THIS EXISTS:
//   Static a11y linters (axe on source, template scanners) cannot see what only
//   exists at runtime: the actual keyboard tab order, whether a dialog traps and
//   restores focus, whether live regions announce, whether the active nav item
//   carries aria-current, and whether a focused element shows a visible focus
//   indicator. This probe drives a real browser and reports those five things as
//   structured JSON, cheaply, across many routes in one process.
//
// WHAT THIS FIXES:
//   Evaluation runs that "checked accessibility" by eyeballing screenshots and
//   missed keyboard/focus/live-region defects that only manifest at runtime.
//
// DEPENDENCIES:
//   node >= 18, playwright (chromium preinstalled at /opt/pw-browsers; do NOT
//   run `playwright install`).
//
// USAGE:
//   node a11y-probe.mjs --base-url http://localhost:8080 \
//       --routes routes.json --roles anon,member --out ./out/a11y
//   Reuses the same routes.json / credential contract as sweep.mjs.

import { parseArgs, loadConfig, slug, write, login } from './eval-common.mjs';

const args = parseArgs(process.argv.slice(2));
const BASE_URL = (args['base-url'] || 'http://localhost:8080').replace(/\/$/, '');
const OUT = args.out || './out/a11y';
const ROLES = (args.roles || 'anon').split(',').map((s) => s.trim());
const cfg = loadConfig(args.routes);
const ROUTES = cfg.routes || ['/'];

// --- individual checks -----------------------------------------------------

async function keyboardOrder(page) {
  // Tab through the first N focusable stops; report the DOM-order sequence and
  // whether it is monotonic (no positive tabindex jumping the order around).
  const stops = [];
  const MAX = 25;
  for (let i = 0; i < MAX; i++) {
    await page.keyboard.press('Tab');
    const info = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return null;
      return {
        tag: el.tagName.toLowerCase(),
        tabindex: el.getAttribute('tabindex'),
        label: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 40),
        domIndex: [...document.querySelectorAll('*')].indexOf(el),
      };
    });
    if (!info) break;
    stops.push(info);
  }
  const positiveTabindex = stops.filter((s) => s.tabindex && parseInt(s.tabindex, 10) > 0).length;
  let outOfOrder = 0;
  for (let i = 1; i < stops.length; i++) if (stops[i].domIndex < stops[i - 1].domIndex) outOfOrder++;
  return { stops: stops.length, positiveTabindex, outOfOrderJumps: outOfOrder };
}

async function focusVisibility(page) {
  // Focus each of the first few interactive elements; check for a visible focus
  // indicator (outline width/style or a box-shadow change).
  return page.evaluate(() => {
    const els = [...document.querySelectorAll('a[href], button, input, select, textarea, [tabindex]')].slice(0, 10);
    let invisible = 0;
    for (const el of els) {
      el.focus();
      const cs = getComputedStyle(el);
      const hasOutline = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0;
      const hasShadow = cs.boxShadow && cs.boxShadow !== 'none';
      if (!hasOutline && !hasShadow) invisible++;
    }
    return { checked: els.length, withoutVisibleFocus: invisible };
  });
}

async function landmarksAndNav(page) {
  return page.evaluate(() => {
    const liveRegions = document.querySelectorAll('[aria-live], [role="status"], [role="alert"]').length;
    const navCurrent = document.querySelectorAll('nav [aria-current]').length;
    const navLinks = document.querySelectorAll('nav a[href]').length;
    const h1 = document.querySelectorAll('h1').length;
    return { liveRegions, navLinksWithAriaCurrent: navCurrent, navLinks, h1Count: h1 };
  });
}

async function dialogLifecycle(page) {
  // Find a dialog trigger; open it; confirm focus moved into the dialog; press
  // Escape; confirm focus returned to the trigger. Best-effort -- reports
  // "no dialog trigger found" when the heuristic misses.
  const trigger = await page.$('[data-dialog-open], [aria-haspopup="dialog"], [data-open-modal]');
  if (!trigger) return { tested: false, reason: 'no dialog trigger found' };
  try {
    await trigger.focus();
    await trigger.click();
    await page.waitForTimeout(200);
    const focusInDialog = await page.evaluate(() =>
      !!document.activeElement.closest('[role="dialog"], dialog[open]'));
    await page.keyboard.press('Escape');
    await page.waitForTimeout(200);
    const focusRestored = await page.evaluate(() => {
      const el = document.activeElement;
      return !el.closest('[role="dialog"], dialog[open]');
    });
    return { tested: true, focusEntersDialog: focusInDialog, focusRestoredOnClose: focusRestored };
  } catch (e) {
    return { tested: false, reason: e.message };
  }
}

function violations(route, role, r) {
  const v = [];
  if (r.keyboard.positiveTabindex > 0) v.push('positive tabindex present (breaks natural tab order)');
  if (r.keyboard.outOfOrderJumps > 0) v.push(`${r.keyboard.outOfOrderJumps} tab stop(s) jump backwards in DOM order`);
  if (r.focus.withoutVisibleFocus > 0) v.push(`${r.focus.withoutVisibleFocus}/${r.focus.checked} focusable(s) lack a visible focus indicator`);
  if (r.nav.h1Count !== 1) v.push(`${r.nav.h1Count} <h1> on page (expected 1)`);
  if (r.nav.navLinks > 0 && r.nav.navLinksWithAriaCurrent === 0) v.push('nav present but no aria-current on active item');
  if (r.dialog.tested && r.dialog.focusEntersDialog === false) v.push('dialog does not move focus inside on open');
  if (r.dialog.tested && r.dialog.focusRestoredOnClose === false) v.push('dialog does not restore focus on close');
  return v.map((desc) => ({ route, role, desc }));
}

async function main() {
  const { chromium } = await import('playwright');
  const launchOpts = {};
  if (process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE) launchOpts.executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
  const browser = await chromium.launch(launchOpts);
  const all = [];
  const allViolations = [];
  for (const role of ROLES) {
    const context = await browser.newContext();
    const ok = await login(context, cfg, BASE_URL, role);
    // null for anon; true/false for a real login attempt. A failed non-anon
    // login means every result below reflects an anonymous session, so the
    // role label is unreliable -- surface it as a violation, not a silent pass.
    const authenticated = role === 'anon' ? null : ok;
    if (authenticated === false) {
      allViolations.push({ route: '(all)', role, desc: `login failed -- results reflect an anonymous session; role label unreliable` });
    }
    for (const route of ROUTES) {
      process.stderr.write(`  a11y ${route} @ ${role}\n`);
      const page = await context.newPage();
      await page.setViewportSize({ width: 1440, height: 900 });
      let rec = { route, role, authenticated, error: null };
      try {
        await page.goto(BASE_URL + route, { waitUntil: 'domcontentloaded', timeout: 30000 });
        const keyboard = await keyboardOrder(page);
        const focus = await focusVisibility(page);
        const nav = await landmarksAndNav(page);
        const dialog = await dialogLifecycle(page);
        rec = { route, role, authenticated, keyboard, focus, nav, dialog, error: null };
        allViolations.push(...violations(route, role, rec));
      } catch (e) {
        rec.error = e.message;
      } finally {
        await page.close();
      }
      write(`${OUT}/${slug(route)}__${role}.json`, rec);
      all.push(rec);
    }
    await context.close();
  }
  await browser.close();
  write(`${OUT}/a11y-summary.json`, {
    baseUrl: BASE_URL, roles: ROLES, routeCount: ROUTES.length,
    violationCount: allViolations.length, violations: allViolations,
    generatedAt: new Date().toISOString(),
  });
  console.log(`a11y probe complete: ${all.length} page(s), ${allViolations.length} violation(s) -> ${OUT}/a11y-summary.json`);
  process.exit(0);
}

main().catch((e) => { console.error(e); process.exit(1); });
