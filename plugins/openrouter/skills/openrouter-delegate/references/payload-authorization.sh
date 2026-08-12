#!/usr/bin/env bash
# Automatic, content-free unchanged-byte proof for OpenRouter delegation.
# This helper never asks for approval. `snapshot` records exact ordered bytes;
# `verify-trusted-boundary` reruns the disclosure boundary and proves those
# bytes are unchanged immediately before provider contact.

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

MODE="${1:-}"
[ -n "$MODE" ] || {
  echo "payload-authorization: snapshot|verify-trusted-boundary required" >&2
  exit 2
}
shift

MANIFEST=""
POLICY=""
CONTENT_FILES=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --output|--manifest)
      [ "$#" -ge 2 ] || { echo "payload-authorization: missing argument" >&2; exit 2; }
      MANIFEST="$2"; shift 2;;
    --policy)
      [ "$#" -ge 2 ] || { echo "payload-authorization: missing argument" >&2; exit 2; }
      POLICY="$2"; shift 2;;
    --content-file)
      [ "$#" -ge 2 ] || { echo "payload-authorization: missing argument" >&2; exit 2; }
      CONTENT_FILES+=("$2"); shift 2;;
    *) echo "payload-authorization: unknown argument" >&2; exit 2;;
  esac
done

case "$MODE" in
  snapshot)
    [ -n "$MANIFEST" ] && [ "${#CONTENT_FILES[@]}" -gt 0 ] || {
      echo "payload-authorization: output and content files required" >&2
      exit 2
    }
    ;;
  verify-trusted-boundary)
    [ -n "$MANIFEST" ] && [ -n "$POLICY" ] &&
      [ "${#CONTENT_FILES[@]}" -gt 0 ] || {
      echo "payload-authorization: manifest, policy, and content files required" >&2
      exit 2
    }
    ;;
  *)
    echo "payload-authorization: snapshot|verify-trusted-boundary required" >&2
    exit 2
    ;;
esac

for content_file in "${CONTENT_FILES[@]}"; do
  [ -f "$content_file" ] && [ -r "$content_file" ] || {
    echo "payload-authorization: content file unavailable" >&2
    exit 2
  }
done

if [ "$MODE" = "verify-trusted-boundary" ]; then
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  BOUNDARY="$SCRIPT_DIR/delegation-boundary.sh"
  BOUNDARY_ARGS=()
  [ -x "$BOUNDARY" ] && [ -r "$POLICY" ] || {
    echo "payload-authorization: trusted boundary unavailable" >&2
    exit 2
  }
  for content_file in "${CONTENT_FILES[@]}"; do
    BOUNDARY_ARGS+=(--content-file "$content_file")
  done
  "$BOUNDARY" --mode artifact-delegation --policy "$POLICY" \
    "${BOUNDARY_ARGS[@]}" >/dev/null
fi

PAYLOAD_AUTH_MODE="$MODE" python3 -I - "$MANIFEST" \
  "${CONTENT_FILES[@]}" <<'PY'
import hashlib
import json
import os
import tempfile
from pathlib import Path
import sys


mode = os.environ["PAYLOAD_AUTH_MODE"]
manifest_path, *content_paths = sys.argv[1:]


def fail(message: str) -> None:
    print(f"payload-authorization: {message}", file=sys.stderr)
    raise SystemExit(2)


def build_manifest() -> dict:
    payload = hashlib.sha256()
    files = []
    for index, path in enumerate(content_paths):
        try:
            data = Path(path).read_bytes()
        except OSError:
            fail("content file unreadable")
        payload.update(index.to_bytes(8, "big"))
        payload.update(len(data).to_bytes(8, "big"))
        payload.update(data)
        files.append({
            "index": index,
            "byteCount": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    return {
        "schemaVersion": 1,
        "authorizationScope": "policy-screened-ordered-content-bytes",
        "payloadSha256": payload.hexdigest(),
        "files": files,
    }


current = build_manifest()
target = Path(manifest_path)
if mode == "snapshot":
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(current, handle, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, target)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    print(current["payloadSha256"])
    raise SystemExit(0)

try:
    recorded = json.loads(target.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    fail("snapshot manifest unreadable")
if recorded != current:
    fail("payload changed after automatic screening snapshot")
print(json.dumps({
    "authorizationMode": "trusted-boundary",
    "authorizationScope": "policy-accepted-unchanged-ordered-content-bytes",
    "payloadSha256": current["payloadSha256"],
}, sort_keys=True))
PY
