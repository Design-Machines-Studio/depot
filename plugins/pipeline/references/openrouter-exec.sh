#!/usr/bin/env bash
# Retired provider-bearing Pipeline entry point. Bounded external writes moved
# to model-router and are reachable only through a role request.
set -euo pipefail
printf '%s\n' 'openrouter-exec: retired; request builder-fast or builder-deep through model-router' >&2
exit 76
