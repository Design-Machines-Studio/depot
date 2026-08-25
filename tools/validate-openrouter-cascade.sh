#!/usr/bin/env bash
# Compatibility release gate: the former Pipeline-owned model cascade is now
# model-router's role resolver. Keep this entry point for repository automation.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"$ROOT/tools/test-model-router.sh"
"$ROOT/tools/validate-provider-neutral-routing.sh"
printf '%s\n' 'OK    provider-neutral model-router boundary valid'
