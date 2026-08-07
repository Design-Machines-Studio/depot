#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO_BIN="/usr/local/go/bin/go"
GO_CACHE="${TMPDIR:-/tmp}/workflow-authority-go-cache"
MODULE="$ROOT/native/workflow-authority"
LIBFIDO2_VERSION="1.17.0"
REQUIRE_PRODUCTION_BUILD="${WORKFLOW_AUTHORITY_REQUIRE_PRODUCTION_BUILD:-0}"

if [[ "$REQUIRE_PRODUCTION_BUILD" != "0" && "$REQUIRE_PRODUCTION_BUILD" != "1" ]]; then
  printf 'FAIL  WORKFLOW_AUTHORITY_REQUIRE_PRODUCTION_BUILD must be 0 or 1\n' >&2
  exit 1
fi

if [[ ! -x "$GO_BIN" ]]; then
  printf 'FAIL  exact Go launcher unavailable: %s\n' "$GO_BIN" >&2
  exit 1
fi

version="$(cd "$MODULE" && GOTOOLCHAIN=auto GOCACHE="$GO_CACHE" "$GO_BIN" env GOVERSION)"
if [[ "$version" != "go1.26.5" ]]; then
  printf 'FAIL  workflow authority requires Go 1.26.5, got %s\n' "$version" >&2
  exit 1
fi

(
  cd "$MODULE"
  GOTOOLCHAIN=auto GOCACHE="$GO_CACHE" "$GO_BIN" test ./...
  GOTOOLCHAIN=auto GOCACHE="$GO_CACHE" "$GO_BIN" test -race ./...
  GOTOOLCHAIN=auto GOCACHE="$GO_CACHE" "$GO_BIN" vet ./...
  GOTOOLCHAIN=auto GOCACHE="$GO_CACHE" "$GO_BIN" build ./cmd/workflow-authority ./cmd/workflow-authorityd
)

# --- M0/M1 fixture isolation, secret surface, and acceptance harness ---------
#
# Everything above is the Go build and test gate and is unchanged. The checks
# below are additive: none of them replaces or relaxes a check above.

# The fixture scaffolding must be unreachable from any untagged build. If it
# ever leaks into `go build ./...` it stops being test-only scaffolding and
# becomes a shipped code path.
untagged_packages="$(cd "$MODULE" && GOTOOLCHAIN=auto GOCACHE="$GO_CACHE" "$GO_BIN" list ./...)"
if printf '%s\n' "$untagged_packages" | grep -q 'workflow-authority-fixture'; then
  printf 'FAIL  fixture scaffolding is reachable from an untagged build\n' >&2
  exit 1
fi

tagged_packages="$(cd "$MODULE" && GOTOOLCHAIN=auto GOCACHE="$GO_CACHE" "$GO_BIN" list -tags fixture ./...)"
if ! printf '%s\n' "$tagged_packages" | grep -q 'workflow-authority-fixture'; then
  printf 'FAIL  fixture entrypoint is missing under -tags fixture\n' >&2
  exit 1
fi

(
  cd "$MODULE"
  GOTOOLCHAIN=auto GOCACHE="$GO_CACHE" "$GO_BIN" vet -tags fixture ./...
  GOTOOLCHAIN=auto GOCACHE="$GO_CACHE" "$GO_BIN" build -tags fixture ./...
)

# Secret surface. Credential-shaped literals must never appear in the authority
# module or its harness. The product's own scanner pattern table is not a match:
# a bracket expression such as AKIA[0-9A-Z]{16} does not satisfy the pattern it
# describes.
secret_hits="$(grep -R -E -n \
  -e 'AKIA[0-9A-Z]{16}' \
  -e 'sk-or-v1-[A-Za-z0-9]{16,}' \
  -e 'sk-ant-[A-Za-z0-9-]{16,}' \
  -e 'gh[pousr]_[A-Za-z0-9]{20,}' \
  -e 'github_pat_[A-Za-z0-9_]{20,}' \
  -e 'glpat-[A-Za-z0-9_-]{16,}' \
  -e '-----BEGIN [A-Z ]*PRIVATE KEY-----' \
  "$MODULE" "$ROOT/tests/test_workflow_authority_integration.py" 2>/dev/null || true)"
if [ -n "$secret_hits" ]; then
  printf 'FAIL  credential-shaped literal in the authority module or harness:\n%s\n' "$secret_hits" >&2
  exit 1
fi

# Calendar-date literals. ipc.Server.handle applies the allocation ExpiresAt as
# a real net.Conn deadline, so a frozen date in a fixture expires every
# connection the moment that date passes. Prose in comments is exempt; code
# literals are not.
fixture_sources="$MODULE/cmd/workflow-authority-fixture $MODULE/internal/client/fixture_runner.go $ROOT/tests/test_workflow_authority_integration.py"
date_hits="$(grep -R -E -n \
  -e 'time\.Date\(' \
  -e '"(19|20)[0-9]{2}-[0-9]{2}-[0-9]{2}' \
  $fixture_sources 2>/dev/null || true)"
if [ -n "$date_hits" ]; then
  printf 'FAIL  calendar-date literal in fixture sources:\n%s\n' "$date_hits" >&2
  exit 1
fi

# Black-box acceptance harness. The module is skipped unless
# WORKFLOW_AUTHORITY_E2E=1, so this gate is the only place it runs -- and a
# module that silently skips inside its own gate is an empty result read as a
# pass. Assert that tests actually ran.
PYTHON=""
for CANDIDATE in python3 python3.13 python3.12; do
  if command -v "$CANDIDATE" >/dev/null 2>&1 && \
     "$CANDIDATE" -I -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1; then
    PYTHON="$(command -v "$CANDIDATE")"
    break
  fi
done
if [ -z "$PYTHON" ]; then
  printf 'FAIL  python3 >= 3.12 not found for the acceptance harness\n' >&2
  exit 1
fi

harness_log="$(mktemp "${TMPDIR:-/tmp}/workflow-authority-harness.XXXXXX")"
trap 'rm -f "$harness_log"' EXIT
# tests/__init__.py imports workflow_kernel at module level, so the harness
# cannot be collected without the kernel references on PYTHONPATH.
if ! (cd "$ROOT" && WORKFLOW_AUTHORITY_E2E=1 \
      PYTHONPATH="$ROOT/plugins/workflow-kernel/skills/workflow-kernel/references" \
      "$PYTHON" -m unittest -v tests.test_workflow_authority_integration) > "$harness_log" 2>&1; then
  printf 'FAIL  workflow authority acceptance harness failed:\n' >&2
  cat "$harness_log" >&2
  exit 1
fi
# unittest counts skipped cases inside "Ran N tests", so N alone cannot
# distinguish a real run from a wholly skipped module -- which is precisely the
# false green this gate exists to prevent. Subtract the reported skips and
# require at least one case to have actually executed.
# `|| true` on both pipelines: under `set -o pipefail` a grep that matches
# nothing fails the whole pipeline and, with `set -e`, kills the script before
# it can report anything. A missing summary must reach the explicit check
# below, and a run with no skips legitimately has no skipped= line.
harness_ran="$( { grep -E '^Ran [0-9]+ test' "$harness_log" || true; } | sed -E 's/^Ran ([0-9]+) test.*/\1/' | tail -1)"
harness_skipped="$( { grep -E '^OK \(skipped=[0-9]+\)' "$harness_log" || true; } | sed -E 's/^OK \(skipped=([0-9]+)\).*/\1/' | tail -1)"
[ -n "$harness_skipped" ] || harness_skipped=0
if [ -z "$harness_ran" ]; then
  printf 'FAIL  acceptance harness produced no unittest summary\n' >&2
  cat "$harness_log" >&2
  exit 1
fi
harness_executed=$((harness_ran - harness_skipped))
if [ "$harness_executed" -lt 1 ]; then
  printf 'FAIL  acceptance harness executed %s cases (%s ran, %s skipped); an all-skipped run is not a pass\n' \
    "$harness_executed" "$harness_ran" "$harness_skipped" >&2
  cat "$harness_log" >&2
  exit 1
fi
printf 'OK    workflow authority acceptance harness executed %s cases (%s skipped)\n' "$harness_executed" "$harness_skipped"
grep -E '^  GAP  ' "$harness_log" || true

installed_libfido2=""
if [[ "$(uname -s)" == "Linux" ]] && command -v pkg-config >/dev/null 2>&1; then
  installed_libfido2="$(pkg-config --modversion libfido2 2>/dev/null || true)"
fi

if [[ "$(uname -s)" == "Linux" && "$installed_libfido2" == "$LIBFIDO2_VERSION" ]]; then
  (
    cd "$MODULE"
    GOTOOLCHAIN=auto GOCACHE="$GO_CACHE" "$GO_BIN" test -tags libfido2 ./...
    GOTOOLCHAIN=auto GOCACHE="$GO_CACHE" "$GO_BIN" test -race -tags libfido2 ./...
    GOTOOLCHAIN=auto GOCACHE="$GO_CACHE" "$GO_BIN" vet -tags libfido2 ./...
    GOTOOLCHAIN=auto GOCACHE="$GO_CACHE" "$GO_BIN" build -tags libfido2 ./cmd/workflow-authority ./cmd/workflow-authorityd
  )
  printf 'OK    workflow authority fixture and production libfido2 validation passed with %s and libfido2 %s\n' "$version" "$LIBFIDO2_VERSION"
else
  if [[ "$REQUIRE_PRODUCTION_BUILD" == "1" ]]; then
    printf 'FAIL  pinned production build requires Linux, pkg-config, and exactly libfido2 %s; host=%s libfido2=%s\n' "$LIBFIDO2_VERSION" "$(uname -s)" "${installed_libfido2:-unavailable}" >&2
    exit 1
  fi
  printf 'COVERAGE-GAP workflow authority production build requires Linux and libfido2 %s; portable fixture validation passed with %s\n' "$LIBFIDO2_VERSION" "$version"
fi
