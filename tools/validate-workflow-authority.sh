#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO_BIN="/usr/local/go/bin/go"
GO_CACHE="${TMPDIR:-/tmp}/workflow-authority-go-cache"
MODULE="$ROOT/native/workflow-authority"

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
)

printf 'OK    workflow authority local fixture validation passed with %s\n' "$version"
