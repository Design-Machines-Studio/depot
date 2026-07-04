#!/usr/bin/env node
// eval-common.mjs -- shared harness for sweep.mjs and a11y-probe.mjs.
//
// WHY THIS EXISTS:
//   sweep.mjs and a11y-probe.mjs both need identical arg parsing, route/config
//   loading, output writing, and the login choreography. Duplicating those ~60
//   lines across the two scripts let them silently drift -- the two copies of
//   login()/creds() already diverged (one logged diagnostics, one swallowed
//   errors). This module is the single source both import, so the credential
//   contract and login flow are authored and fixed once.
//
// WHAT THIS FIXES:
//   Copy-paste drift between the two probe scripts and double-maintenance of
//   the credential/login contract.
//
// DEPENDENCIES:
//   node >= 18. Imported by sibling references/*.mjs via `import` -- still a
//   single `node` invocation, so the standalone-script contract holds (the
//   convention governs the shebang/header/exec-bit contract, not intra-dir
//   imports).
//
// USAGE:
//   import { parseArgs, loadConfig, slug, write, creds, login } from './eval-common.mjs';

import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';

export function parseArgs(argv) {
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

// Load the route/login config from --routes, or fall back to the single root
// route when it is omitted.
export function loadConfig(routesArg) {
  return routesArg ? JSON.parse(readFileSync(routesArg, 'utf8')) : { routes: ['/'] };
}

export const slug = (s) => s.replace(/[^a-z0-9]+/gi, '_').replace(/^_|_$/g, '') || 'root';

export function write(path, data) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, typeof data === 'string' ? data : JSON.stringify(data, null, 2));
}

// Credentials for a role: env (EVAL_<ROLE>_EMAIL / EVAL_<ROLE>_PASSWORD) wins,
// then cfg.login.roles[role], else null.
export function creds(cfg, role) {
  const R = role.toUpperCase();
  const fromEnv = process.env[`EVAL_${R}_EMAIL`] && {
    email: process.env[`EVAL_${R}_EMAIL`], password: process.env[`EVAL_${R}_PASSWORD`],
  };
  return fromEnv || (cfg.login && cfg.login.roles && cfg.login.roles[role]) || null;
}

// Attempt to authenticate `context` as `role`. Returns true when the role is
// authenticated (or is anon / no login is configured). Returns false when a
// non-anon role could NOT authenticate -- the caller must then treat that cell
// as anon-equivalent and flag the role label as unreliable rather than trust it.
export async function login(context, cfg, baseUrl, role) {
  if (role === 'anon' || !cfg.login) return true;
  const c = creds(cfg, role);
  if (!c) { console.error(`  ! no credentials for role ${role}; treating as anon`); return false; }
  const page = await context.newPage();
  try {
    await page.goto(baseUrl + (cfg.login.url || '/login'), { waitUntil: 'domcontentloaded' });
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
