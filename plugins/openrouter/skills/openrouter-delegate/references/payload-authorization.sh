#!/usr/bin/env bash
# Content-free, byte-bound authorization receipt for OpenRouter delegation.
# `verify` checks a user-approved exact digest. `verify-trusted-boundary` is an
# explicit automation mode: it reruns the canonical disclosure boundary and
# verifies unchanged bytes immediately before network transmission.
#
# `batch-approve` and `verify-batch` implement the INTERIM operator-batch mode.
# One interactive approval per run covers a digest-bound payload set, so
# automated lanes stop needing one approval per payload. For payloads that
# travel this path the mode changes approval GRANULARITY rather than approval
# EXISTENCE: only exact digests recorded in the batch file are accepted, and
# everything else falls back to the per-payload interactive path or fails
# closed.
#
# HONESTY NOTE -- what the batch artifact is, and what it is not.
# The batch file is PROCEDURAL and UNAUTHENTICATED. It is bare JSON with no
# signature, no MAC, and no user-presence binding, so nothing in it proves that
# `batch-approve` -- or its /dev/tty confirmation -- ever ran. Any process
# running as the same user, including the very agent this gate is meant to
# constrain, can hand-write a batch file carrying its own payload digests and
# this run's id and enter interim mode with no interactive approval at all. The
# run id, expiry, and sunset checks all validate data that such a forger
# supplies.
# The interactive confirmation is therefore a control against ACCIDENTAL and
# AUTOMATED entry by this tooling. It is NOT a technical barrier against a
# same-user process that forges the artifact.
# Closing that same-user gap is exactly what the out-of-process Workflow
# Authority Broker does, and it is the primary reason this mode carries a
# sunset. Do not answer this with a Keychain ACL or a shared-secret MAC here:
# same-user enforcement inside a script the same user can read and edit is
# theatre, not a control.
#
# Interim-mode invariants (true as written, and no stronger):
#   - batch-approve reads its confirmation from the controlling terminal only.
#     No environment variable substitutes for the interactive confirmation.
#   - A Workflow Authority Broker installed on this host withholds the mode. A
#     probe reporting ready retires it outright: both batch modes refuse with
#     "broker available; interim mode retired on this host". An installed
#     client whose probe errors, is unparseable, or does not report ready is an
#     UNKNOWN state and also refuses, with reason broker_present_not_ready.
#   - `program_sunset` is a hard calendar backstop (2026-09-07). After it,
#     batch files fail validation and extending it requires a reviewed commit
#     that changes PROGRAM_SUNSET here.
#
# Usage:
#   payload-authorization.sh snapshot --output <manifest> --content-file <f>...
#   payload-authorization.sh verify --manifest <m> --approved-sha256 <hex> \
#     --content-file <f>...
#   payload-authorization.sh verify-trusted-boundary --manifest <m> \
#     --policy <p> --content-file <f>...
#   payload-authorization.sh batch-approve --batch-file <out> --run-id <id> \
#     --operator <name> --scope-note <text> \
#     --lane <lane-id>=<lane-manifest> [--lane ...] [--expires-in <seconds>]
#   payload-authorization.sh verify-batch --batch-file <b> --run-id <id> \
#     --manifest <m> --content-file <f>...

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

# Fixed, non-overridable probe path. A caller-selected probe path would let the
# interim mode outlive a ready broker, which is the one downgrade this mode is
# not allowed to buy.
BROKER_CLIENT="/usr/local/bin/workflow-authority"
PROGRAM_SUNSET="2026-09-07"
BATCH_CONFIRMATION_PHRASE="APPROVE INTERIM BATCH"

# Three broker states, not two. "absent" is the only one that leaves interim
# mode available. A client that is installed but whose probe errors, is
# unparseable, or does not report ready is an UNKNOWN state: it fails closed
# rather than widening exposure on a host that is mid-install or degraded.
# The probe is parsed with jq, not a substring glob. A glob yields false
# positives on unrelated "ready" substrings (safe: wrongly refuses) and false
# negatives on formatting variations of a genuine ready status (unsafe: interim
# mode would proceed above a ready broker). A missing jq or unparseable probe
# resolves to present_not_ready, which refuses.
broker_state() {
  if [ ! -x "$BROKER_CLIENT" ]; then
    printf 'absent'
    return 0
  fi
  local probe=""
  if ! probe="$("$BROKER_CLIENT" probe --format json 2>/dev/null)"; then
    printf 'present_not_ready'
    return 0
  fi
  if ! command -v jq >/dev/null 2>&1; then
    printf 'present_not_ready'
    return 0
  fi
  if printf '%s' "$probe" | jq -e '.status == "ready"' >/dev/null 2>&1; then
    printf 'ready'
    return 0
  fi
  printf 'present_not_ready'
}

refuse_when_broker_ready() {
  local state=""
  state="$(broker_state)"
  case "$state" in
    ready)
      echo "payload-authorization: broker available; interim mode retired on this host" >&2
      exit 2
      ;;
    present_not_ready)
      echo "payload-authorization: broker_present_not_ready; broker client is installed but does not probe ready -- interim mode withheld" >&2
      exit 2
      ;;
    absent)
      : # the only state that leaves interim mode available
      ;;
    *)
      # Empty or unrecognized. An unresolved state is not an absent broker.
      echo "payload-authorization: broker state unresolved; interim mode withheld" >&2
      exit 2
      ;;
  esac
}

MODE="${1:-}"
[ -n "$MODE" ] || {
  echo "payload-authorization: snapshot|verify|verify-trusted-boundary|batch-approve|verify-batch required" >&2
  exit 2
}
shift

MANIFEST=""
APPROVED_SHA256=""
POLICY=""
BATCH_FILE=""
RUN_ID=""
OPERATOR=""
SCOPE_NOTE=""
EXPIRES_IN="86400"
CONTENT_FILES=()
LANES=()
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
    --batch-file)
      [ "$#" -ge 2 ] || { echo "payload-authorization: missing argument" >&2; exit 2; }
      BATCH_FILE="$2"; shift 2;;
    --run-id)
      [ "$#" -ge 2 ] || { echo "payload-authorization: missing argument" >&2; exit 2; }
      RUN_ID="$2"; shift 2;;
    --operator)
      [ "$#" -ge 2 ] || { echo "payload-authorization: missing argument" >&2; exit 2; }
      OPERATOR="$2"; shift 2;;
    --scope-note)
      [ "$#" -ge 2 ] || { echo "payload-authorization: missing argument" >&2; exit 2; }
      SCOPE_NOTE="$2"; shift 2;;
    --expires-in)
      [ "$#" -ge 2 ] || { echo "payload-authorization: missing argument" >&2; exit 2; }
      EXPIRES_IN="$2"; shift 2;;
    --lane)
      [ "$#" -ge 2 ] || { echo "payload-authorization: missing argument" >&2; exit 2; }
      LANES+=("$2"); shift 2;;
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
  batch-approve)
    [ -n "$BATCH_FILE" ] && [ -n "$RUN_ID" ] && [ -n "$OPERATOR" ] &&
      [ -n "$SCOPE_NOTE" ] && [ "${#LANES[@]}" -gt 0 ] || {
      echo "payload-authorization: batch file, run id, operator, scope note, and lanes required" >&2
      exit 2
    }
    ;;
  verify-batch)
    [ -n "$BATCH_FILE" ] && [ -n "$RUN_ID" ] && [ -n "$MANIFEST" ] &&
      [ "${#CONTENT_FILES[@]}" -gt 0 ] || {
      echo "payload-authorization: batch file, run id, manifest, and content files required" >&2
      exit 2
    }
    ;;
  *) echo "payload-authorization: snapshot|verify|verify-trusted-boundary|batch-approve|verify-batch required" >&2; exit 2;;
esac

if [ "${#CONTENT_FILES[@]}" -gt 0 ]; then
  for content_file in "${CONTENT_FILES[@]}"; do
    [ -f "$content_file" ] || {
      echo "payload-authorization: content file unavailable" >&2
      exit 2
    }
  done
fi

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

if [ "$MODE" = "batch-approve" ]; then
  refuse_when_broker_ready
  PAYLOAD_AUTH_PROGRAM_SUNSET="$PROGRAM_SUNSET" \
  PAYLOAD_AUTH_CONFIRMATION="$BATCH_CONFIRMATION_PHRASE" \
  python3 - "$BATCH_FILE" "$RUN_ID" "$OPERATOR" "$SCOPE_NOTE" "$EXPIRES_IN" "${LANES[@]}" <<'PY'
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

batch_path, run_id, operator, scope_note, expires_in, *lane_specs = sys.argv[1:]
program_sunset = os.environ["PAYLOAD_AUTH_PROGRAM_SUNSET"]
confirmation_phrase = os.environ["PAYLOAD_AUTH_CONFIRMATION"]
MAX_LIFETIME_SECONDS = 86400
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def fail(message):
    print(f"payload-authorization: {message}", file=sys.stderr)
    raise SystemExit(2)


try:
    lifetime = int(expires_in)
except ValueError:
    fail("expires-in must be a positive integer")
if lifetime < 1 or lifetime > MAX_LIFETIME_SECONDS:
    fail("batch authorization lifetime must be between 1 and 86400 seconds")

now = datetime.now(timezone.utc).replace(microsecond=0)
sunset = datetime.strptime(program_sunset, "%Y-%m-%d").replace(tzinfo=timezone.utc)
if now >= sunset:
    fail(
        "interim operator-batch program sunset "
        f"{program_sunset} has passed; re-issue the sunset in the schema by commit"
    )

lanes = []
digests = []
total_bytes = 0
for spec in lane_specs:
    if "=" not in spec:
        fail("lane must be <lane-id>=<lane-manifest>")
    lane_id, manifest_path = spec.split("=", 1)
    if not lane_id or not manifest_path:
        fail("lane must be <lane-id>=<lane-manifest>")
    try:
        recorded = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        fail("lane authorization manifest unreadable")
    if recorded.get("schemaVersion") != 1:
        fail("lane authorization manifest schema unsupported")
    digest = recorded.get("payloadSha256", "")
    if not isinstance(digest, str) or not HEX64.match(digest):
        fail("lane authorization manifest digest malformed")
    lane_bytes = 0
    for entry in recorded.get("files", []):
        count = entry.get("byteCount")
        if not isinstance(count, int) or count < 0:
            fail("lane authorization manifest byte count malformed")
        lane_bytes += count
    if digest in digests:
        fail("duplicate lane payload digest")
    digests.append(digest)
    lanes.append((lane_id, digest, lane_bytes))
    total_bytes += lane_bytes

expires_at = now + timedelta(seconds=lifetime)

# The confirmation is read from the controlling terminal and nowhere else.
# No environment variable substitutes for the interactive confirmation.
try:
    tty_out = open("/dev/tty", "w", encoding="utf-8")
    tty_in = open("/dev/tty", "r", encoding="utf-8")
except OSError:
    fail("interactive confirmation unavailable; interim batch mode fails closed")

with tty_out, tty_in:
    tty_out.write("\n")
    tty_out.write("INTERIM operator-batch authorization for OpenRouter lanes\n")
    tty_out.write("This is a temporary, sunset-bound loosening of approval\n")
    tty_out.write("granularity. It does not grant broker authority.\n\n")
    tty_out.write(f"  run_id        : {run_id}\n")
    tty_out.write(f"  operator      : {operator}\n")
    tty_out.write(f"  scope_note    : {scope_note}\n")
    tty_out.write(f"  created_at    : {now.strftime('%Y-%m-%dT%H:%M:%SZ')}\n")
    tty_out.write(f"  expires_at    : {expires_at.strftime('%Y-%m-%dT%H:%M:%SZ')}\n")
    tty_out.write(f"  program_sunset: {program_sunset}\n")
    tty_out.write(f"  digest count  : {len(digests)}\n")
    tty_out.write(f"  total bytes   : {total_bytes}\n\n")
    tty_out.write("Lanes covered by this single approval:\n")
    for lane_id, digest, lane_bytes in lanes:
        tty_out.write(f"  {lane_id}  {lane_bytes} bytes  sha256:{digest}\n")
    tty_out.write(
        "\nOnly these exact digests become automated. Any other payload falls\n"
        "back to per-payload interactive approval or fails closed.\n"
    )
    tty_out.write(f"\nType exactly '{confirmation_phrase}' to authorize: ")
    tty_out.flush()
    answer = tty_in.readline()

if answer.strip() != confirmation_phrase:
    fail("interim batch authorization declined by operator")

document = {
    "schema_version": 1,
    "authorization_mode": "interim_operator_batch",
    "run_id": run_id,
    "operator": operator,
    "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "expires_at": expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "payload_digests": digests,
    "scope_note": scope_note,
    "program_sunset": program_sunset,
}

target = Path(batch_path)
target.parent.mkdir(parents=True, exist_ok=True)
fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(document, handle, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, target)
except Exception:
    try:
        os.unlink(temporary)
    except OSError:
        pass
    raise

print(hashlib.sha256(target.read_bytes()).hexdigest())
PY
  exit 0
fi

if [ "$MODE" = "verify-batch" ]; then
  refuse_when_broker_ready
fi

PAYLOAD_AUTH_PROGRAM_SUNSET="$PROGRAM_SUNSET" \
PAYLOAD_AUTH_BATCH_FILE="$BATCH_FILE" \
PAYLOAD_AUTH_RUN_ID="$RUN_ID" \
python3 - "$MODE" "$MANIFEST" "$APPROVED_SHA256" "${CONTENT_FILES[@]}" <<'PY'
import hashlib
import hmac
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

mode, manifest_path, approved, *content_paths = sys.argv[1:]

HEX64 = re.compile(r"^[0-9a-f]{64}$")
BATCH_KEYS = {
    "schema_version",
    "authorization_mode",
    "run_id",
    "operator",
    "created_at",
    "expires_at",
    "payload_digests",
    "scope_note",
    "program_sunset",
}
MAX_LIFETIME_SECONDS = 86400


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


def parse_stamp(value, label):
    if not isinstance(value, str):
        fail(f"batch authorization {label} malformed")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        fail(f"batch authorization {label} malformed")


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
if mode == "verify-batch":
    batch_path = Path(os.environ["PAYLOAD_AUTH_BATCH_FILE"])
    run_id = os.environ["PAYLOAD_AUTH_RUN_ID"]
    program_sunset = os.environ["PAYLOAD_AUTH_PROGRAM_SUNSET"]
    try:
        raw = batch_path.read_bytes()
        batch = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        fail("batch authorization unreadable")
    if not isinstance(batch, dict) or set(batch) != BATCH_KEYS:
        fail("batch authorization schema unexpected")
    if batch["schema_version"] != 1:
        fail("batch authorization schema unsupported")
    if batch["authorization_mode"] != "interim_operator_batch":
        fail("batch authorization mode unexpected")
    if not isinstance(batch["operator"], str) or not batch["operator"].strip():
        fail("batch authorization operator missing")
    if not isinstance(batch["scope_note"], str) or not batch["scope_note"].strip():
        fail("batch authorization scope note missing")
    if not isinstance(batch["run_id"], str) or not batch["run_id"]:
        fail("batch authorization run id missing")
    if not hmac.compare_digest(batch["run_id"], run_id):
        fail("batch authorization was issued for a different run")
    if batch["program_sunset"] != program_sunset:
        fail("batch authorization program sunset does not match this release")
    created_at = parse_stamp(batch["created_at"], "created_at")
    expires_at = parse_stamp(batch["expires_at"], "expires_at")
    if expires_at <= created_at:
        fail("batch authorization expiry precedes issuance")
    if expires_at - created_at > timedelta(seconds=MAX_LIFETIME_SECONDS):
        fail("batch authorization lifetime exceeds 24h")
    sunset = datetime.strptime(program_sunset, "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )
    now = datetime.now(timezone.utc)
    if now >= sunset:
        fail("interim operator-batch program sunset has passed")
    if now >= expires_at:
        fail("batch authorization expired")
    if now < created_at:
        fail("batch authorization issued in the future")
    digests = batch["payload_digests"]
    if not isinstance(digests, list) or not digests:
        fail("batch authorization carries no payload digests")
    for digest in digests:
        if not isinstance(digest, str) or not HEX64.match(digest):
            fail("batch authorization digest malformed")
    if not any(
        hmac.compare_digest(digest, current["payloadSha256"]) for digest in digests
    ):
        fail("payload digest is not in this run's batch authorization")
    print(json.dumps({
        "authorizationMode": "interim-operator-batch",
        "authorizationScope": "operator-approved-run-batch-exact-content-bytes",
        "payloadSha256": current["payloadSha256"],
        "batchSha256": hashlib.sha256(raw).hexdigest(),
        "runId": batch["run_id"],
        "expiresAt": batch["expires_at"],
        "programSunset": program_sunset,
    }, sort_keys=True))
    raise SystemExit(0)
if not isinstance(approved, str) or len(approved) != 64:
    fail("approved digest malformed")
if not hmac.compare_digest(approved.lower(), current["payloadSha256"]):
    fail("payload digest was not approved")
PY
