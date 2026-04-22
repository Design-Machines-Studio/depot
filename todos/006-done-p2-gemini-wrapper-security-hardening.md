# 006 — P2 — gemini-wrapper.sh security hardening pass

**Status:** pending
**Severity:** P2 (should fix before merge or in immediate follow-up)
**Source:** dm-review on feature/depot-audience-rollout, 2026-04-22
**Reporting agent:** dm-review:review:security-auditor

## Problem

The new `plugins/gemini/skills/gemini-delegate/references/gemini-wrapper.sh` (109 lines bash) has 4 P2 security findings. None are remotely-exploitable on their own; one (ANSI escape injection) becomes exploitable when wrapper is fed crafted external content.

## Findings

### S-1 — Missing `set -euo pipefail` (CWE-754)

Silent failure modes when `mktemp` fails (full TMPDIR or restrictive perms) or `-m` arg has no value. Add at top:

```bash
set -euo pipefail
err_log=$(mktemp -t gemini-wrapper.XXXXXX) || { echo "[gemini-wrapper] mktemp failed" >&2; return 1; }
```

### S-2 — No trap cleanup of temp files (CWE-459 / CWE-377)

Temp files leak to `$TMPDIR` on Ctrl-C / SIGTERM / `set -e` firing. The files contain Gemini stderr (which can include partial prompts, tokens echoed back, stack traces).

Add:

```bash
err_log=""
cleanup() { [ -n "$err_log" ] && rm -f "$err_log"; }
trap cleanup EXIT INT TERM
err_log=$(mktemp -t gemini-wrapper.XXXXXX)
chmod 600 "$err_log"
```

Sourcing complicates `trap EXIT` — guard it or use per-iteration trap when sourced.

### S-3 — PATH hijack vector (CWE-426 / CWE-427)

`export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"` keeps caller's `$PATH`, so a caller setting `PATH=/tmp/evil:...` before invoking can hijack `gemini`/`gtimeout`/`grep`/`cat`/`rm`/`mktemp`.

Fix: Either reset PATH to a fixed value or resolve dependencies via `command -v` once at top and call by absolute path:

```bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
```

### S-4 — ANSI escape injection via stderr passthrough (CWE-150) — **most exploitable**

`cat "$err_log" >&2` forwards Gemini stderr verbatim. If a workflow pipes external content (research target page, PR description, feedback) into the wrapper and Gemini reflects part of it in an error string with ANSI escape sequences, those sequences manipulate the operator's terminal (cursor moves, OSC 52 clipboard hijack, OSC 8 phishing hyperlinks).

Fix: Filter stderr passthrough to printable + newline + tab:

```bash
LC_ALL=C tr -d '\000-\010\013\014\016-\037' < "$err_log" >&2
```

Or pass through `cat -v` for safe escaping.

## Fix order

S-4 first (only finding with realistic external attacker reach). Then S-1 + S-3 together (~5 lines). S-2 last (low exploit value on macOS where user-owned `/var/folders/.../T/` is not world-readable).

## Acceptance

- [ ] S-4: stderr is filtered before passthrough; verified by injecting `\033[H\033[J` test pattern
- [ ] S-1: `set -euo pipefail` added; tested by removing TMPDIR write permissions
- [ ] S-3: PATH reset to fixed value OR dependencies resolved via absolute paths
- [ ] S-2: Trap-based cleanup; verified by Ctrl-C during execution leaves no leftover temp files
- [ ] Wrapper still passes `bash gemini-wrapper.sh -p "say hi"` smoke test after all changes
