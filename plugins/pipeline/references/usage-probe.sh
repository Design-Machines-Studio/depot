#!/usr/bin/env bash
# Retired transport-availability surface. Live evidence is private to
# model-router and must not be projected back into Pipeline.
set -euo pipefail
printf '%s\n' '{"retired":true,"replacement":"model-router role dispatch"}'
