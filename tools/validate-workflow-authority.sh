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
