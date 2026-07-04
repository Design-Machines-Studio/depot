#!/usr/bin/env bash
# curl-probes.sh -- cheapest-signal-first HTTP probes for eval-sweep Phase 1.
#
# WHY THIS EXISTS:
#   A browser is the most expensive way to learn things curl can tell you for
#   nearly free: compression, caching, and error-page headers, plus whether the
#   authed login flow even works. Running these first catches whole classes of
#   defects before a single browser launches, and produces a session cookie the
#   browser sweep can reuse.
#
# WHAT THIS FIXES:
#   Evaluations that spent browser budget discovering a missing Cache-Control or
#   a 200-shell error page that a HEAD request would have surfaced instantly.
#   Also documents the gorilla/csrf gotcha (Assembly): the login POST needs an
#   Origin header or gorilla/csrf rejects it 403.
#
# DEPENDENCIES:
#   curl. (jq optional, only for pretty-printing.)
#
# USAGE:
#   EVAL_LOGIN_PASSWORD='password' \
#     ./curl-probes.sh http://localhost:8080 /login user@example.coop
#   Args: BASE_URL [LOGIN_PATH] [EMAIL]
#   The password comes from EVAL_LOGIN_PASSWORD (an env var), NOT a CLI arg, so
#   it never lands in `ps aux` / /proc/<pid>/cmdline or shell history.
#   The session cookie jar is written to a private mktemp file (outside the
#   repo), never ./out, so a stray `git add` cannot commit a live session token.

# Fixed PATH so a caller-controlled environment cannot hijack curl.
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH

BASE_URL="${1:-http://localhost:8080}"
LOGIN_PATH="${2:-/login}"
EMAIL="${3:-}"
# Password from env only -- keep the live credential out of ps/shell history.
PASSWORD="${EVAL_LOGIN_PASSWORD:-}"
OUT_DIR="./out"
mkdir -p "$OUT_DIR"
# Live session cookie jar goes to a private temp file, NOT the repo working dir,
# so it cannot be accidentally committed. Cleaned up on exit.
COOKIES="$(mktemp -t eval-cookies.XXXXXX)"
trap 'rm -f "$COOKIES"' EXIT

echo "== header probe: ${BASE_URL}/ =="
# -D - dumps response headers; look for Content-Encoding, Cache-Control, ETag.
curl -sS -o /dev/null -D - --compressed "${BASE_URL}/" \
  | grep -iE '^(HTTP/|content-encoding|cache-control|etag|vary|strict-transport|content-type):'

echo
echo "== error-page probe: a route that should 404 =="
# A correct app returns 404 (not a 200 shell) for an unknown route.
STATUS=$(curl -sS -o /dev/null -w '%{http_code}' "${BASE_URL}/this-route-should-not-exist-eval")
echo "unknown route status: ${STATUS} (expected 404)"

echo
echo "== authed login flow =="
if [ -z "$EMAIL" ] || [ -z "$PASSWORD" ]; then
  echo "  (skipped: no EMAIL/PASSWORD provided)"
else
  # Step 1: GET the login page to obtain the CSRF token + cookie.
  #   gorilla/csrf sets a cookie AND embeds a token in a hidden field. We need
  #   both, plus an Origin header on the POST, or the POST is rejected 403.
  LOGIN_HTML=$(curl -sS -c "$COOKIES" "${BASE_URL}${LOGIN_PATH}")
  CSRF=$(printf '%s' "$LOGIN_HTML" \
    | grep -oiE 'name="gorilla.csrf.Token"[^>]*value="[^"]*"' \
    | grep -oiE 'value="[^"]*"' | head -1 | sed -E 's/value="([^"]*)"/\1/')
  if [ -z "$CSRF" ]; then
    # Fall back to a generic csrf_token field name.
    CSRF=$(printf '%s' "$LOGIN_HTML" \
      | grep -oiE 'name="(csrf_token|_csrf)"[^>]*value="[^"]*"' \
      | grep -oiE 'value="[^"]*"' | head -1 | sed -E 's/value="([^"]*)"/\1/')
  fi
  echo "  csrf token: ${CSRF:+present}"

  # Step 2: POST credentials WITH an Origin header (gorilla/csrf requirement).
  POST_STATUS=$(curl -sS -o /dev/null -w '%{http_code}' \
    -b "$COOKIES" -c "$COOKIES" \
    -H "Origin: ${BASE_URL}" \
    --data-urlencode "email=${EMAIL}" \
    --data-urlencode "password=${PASSWORD}" \
    --data-urlencode "gorilla.csrf.Token=${CSRF}" \
    "${BASE_URL}${LOGIN_PATH}")
  echo "  login POST status: ${POST_STATUS} (302/303 = success, 403 = CSRF/Origin problem, 200 = re-render/invalid)"
  echo "  session cookie jar: ${COOKIES}"
fi

echo
echo "done. Findings -> append to findings-ledger.md; this run -> append to commands-log.md."
exit 0
