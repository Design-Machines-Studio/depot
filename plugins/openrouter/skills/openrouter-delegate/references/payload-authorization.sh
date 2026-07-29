#!/usr/bin/env bash
# Content-free, byte-bound authorization receipt for OpenRouter delegation.
# `verify` checks a user-approved exact digest. `verify-trusted-boundary` is an
# explicit automation mode: it reruns the canonical disclosure boundary and
# verifies unchanged bytes immediately before network transmission.

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

MODE="${1:-}"
[ -n "$MODE" ] || {
  echo "payload-authorization: snapshot|verify|verify-trusted-boundary required" >&2
  exit 2
}
shift

MANIFEST=""
APPROVED_SHA256=""
POLICY=""
CONTENT_FILES=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --output|--manifest)
      [ "$#" -ge 2 ] || { echo "payload-authorization: missing argument" >&2; exit 2; }
      MANIFEST="$2"; shift 2;;
    --approved-sha256)
      [ "$#" -ge 2 ] || { echo "payload-authorization: missing argument" >&2; exit 2; }
      APPROVED_SHA256="$2"; shift 2;;
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
  verify)
    [ -n "$MANIFEST" ] && [ -n "$APPROVED_SHA256" ] &&
      [ "${#CONTENT_FILES[@]}" -gt 0 ] || {
      echo "payload-authorization: manifest, approved digest, and content files required" >&2
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
  *) echo "payload-authorization: snapshot|verify|verify-trusted-boundary required" >&2; exit 2;;
esac

for content_file in "${CONTENT_FILES[@]}"; do
  [ -f "$content_file" ] || {
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

python3 - "$MODE" "$MANIFEST" "$APPROVED_SHA256" "${CONTENT_FILES[@]}" <<'PY'
import hashlib
import hmac
import json
import os
import sys
import tempfile
from pathlib import Path

mode, manifest_path, approved, *content_paths = sys.argv[1:]


def fail(message):
    print(f"payload-authorization: {message}", file=sys.stderr)
    raise SystemExit(2)


def build_manifest():
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
        "authorizationScope": "exact-ordered-content-bytes",
        "payloadSha256": payload.hexdigest(),
        "files": files,
    }


current = build_manifest()
if mode == "snapshot":
    target = Path(manifest_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
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
    recorded = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    fail("authorization manifest unreadable")
if recorded != current:
    fail("payload changed after authorization snapshot")
if mode == "verify-trusted-boundary":
    print(json.dumps({
        "authorizationMode": "trusted-boundary",
        "authorizationScope": "policy-accepted-unchanged-ordered-content-bytes",
        "payloadSha256": current["payloadSha256"],
    }, sort_keys=True))
    raise SystemExit(0)
if not isinstance(approved, str) or len(approved) != 64:
    fail("approved digest malformed")
if not hmac.compare_digest(approved.lower(), current["payloadSha256"]):
    fail("payload digest was not approved")
PY
