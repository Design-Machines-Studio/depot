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
#   payload-authorization.sh snapshot-envelope --output <manifest> \
#     --request-file <exact-request.json>
#   payload-authorization.sh verify-envelope --manifest <m> \
#     --approved-sha256 <hex> --request-file <exact-request.json>
#   payload-authorization.sh batch-approve --batch-file <out> --run-id <id> \
#     --operator <name> --scope-note <text> \
#     --lane <lane-id>=<lane-manifest> [--lane ...] [--expires-in <seconds>]
#   payload-authorization.sh validate-batch --batch-file <b> --run-id <id>
#   payload-authorization.sh verify-batch --batch-file <b> --run-id <id> \
#     --lane-id <lane-id> --manifest <m> --request-file <exact-request.json>

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
  echo "payload-authorization: snapshot|snapshot-envelope|verify-envelope|verify|verify-trusted-boundary|batch-approve|validate-batch|verify-batch required" >&2
  exit 2
}
shift

MANIFEST=""
APPROVED_SHA256=""
POLICY=""
BATCH_FILE=""
REQUEST_FILE=""
RUN_ID=""
LANE_ID=""
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
    --request-file)
      [ "$#" -ge 2 ] || { echo "payload-authorization: missing argument" >&2; exit 2; }
      REQUEST_FILE="$2"; shift 2;;
    --run-id)
      [ "$#" -ge 2 ] || { echo "payload-authorization: missing argument" >&2; exit 2; }
      RUN_ID="$2"; shift 2;;
    --lane-id)
      [ "$#" -ge 2 ] || { echo "payload-authorization: missing argument" >&2; exit 2; }
      LANE_ID="$2"; shift 2;;
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
  snapshot-envelope)
    [ -n "$MANIFEST" ] && [ -n "$REQUEST_FILE" ] || {
      echo "payload-authorization: output and request file required" >&2
      exit 2
    }
    ;;
  verify-envelope)
    [ -n "$MANIFEST" ] && [ -n "$APPROVED_SHA256" ] &&
      [ -n "$REQUEST_FILE" ] || {
      echo "payload-authorization: manifest, approved digest, and request file required" >&2
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
      [ -n "$REQUEST_FILE" ] && [ -n "$LANE_ID" ] || {
      echo "payload-authorization: batch file, run id, lane id, manifest, and request file required" >&2
      exit 2
    }
    ;;
  validate-batch)
    [ -n "$BATCH_FILE" ] && [ -n "$RUN_ID" ] || {
      echo "payload-authorization: batch file and run id required" >&2
      exit 2
    }
    ;;
  *) echo "payload-authorization: snapshot|snapshot-envelope|verify-envelope|verify|verify-trusted-boundary|batch-approve|validate-batch|verify-batch required" >&2; exit 2;;
esac

if [ "${#CONTENT_FILES[@]}" -gt 0 ]; then
  for content_file in "${CONTENT_FILES[@]}"; do
    [ -f "$content_file" ] || {
      echo "payload-authorization: content file unavailable" >&2
      exit 2
    }
  done
fi

if [ -n "$REQUEST_FILE" ] && [ ! -f "$REQUEST_FILE" ]; then
  echo "payload-authorization: request file unavailable" >&2
  exit 2
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
  if \
  PAYLOAD_AUTH_PROGRAM_SUNSET="$PROGRAM_SUNSET" \
  PAYLOAD_AUTH_CONFIRMATION="$BATCH_CONFIRMATION_PHRASE" \
  PAYLOAD_AUTH_SELF="$0" \
  python3 - "$BATCH_FILE" "$RUN_ID" "$OPERATOR" "$SCOPE_NOTE" "$EXPIRES_IN" "${LANES[@]}" <<'PY'
import hashlib
import hmac
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import atexit
from datetime import datetime, timedelta, timezone
from pathlib import Path

batch_path, run_id, operator, scope_note, expires_in, *lane_specs = sys.argv[1:]
program_sunset = os.environ["PAYLOAD_AUTH_PROGRAM_SUNSET"]
confirmation_phrase = os.environ["PAYLOAD_AUTH_CONFIRMATION"]
MAX_LIFETIME_SECONDS = 86400
HEX64 = re.compile(r"^[0-9a-f]{64}$")
persisted_batch = None
temporary_handle = None
temporary_path = None
lifecycle_succeeded = False
handling_signal = False
test_failure_stage = (
    os.environ.get("PAYLOAD_AUTH_TEST_FAILURE_STAGE", "")
    if os.environ.get("PAYLOAD_AUTH_TEST_MODE") == "1"
    else ""
)


def cleanup_lifecycle():
    global temporary_handle, temporary_path
    temporary_failed = False
    if temporary_handle is not None:
        try:
            temporary_handle.close()
        except OSError:
            temporary_failed = True
        temporary_handle = None
    if temporary_path is not None:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            temporary_failed = True
    rollback_failed = False
    if persisted_batch is not None and not lifecycle_succeeded:
        try:
            persisted_batch.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            rollback_failed = True
    if temporary_failed:
        print(
            "payload-authorization: temporary batch cleanup failed",
            file=sys.stderr,
        )
    if rollback_failed:
        print(
            "payload-authorization: failed batch authorization rollback",
            file=sys.stderr,
        )


atexit.register(cleanup_lifecycle)


def fail(message):
    print(f"payload-authorization: {message}", file=sys.stderr)
    raise SystemExit(2)


def interrupted(signum, _frame):
    global handling_signal
    if handling_signal:
        return
    handling_signal = True
    for handled_signal in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        signal.signal(handled_signal, signal.SIG_IGN)
    cleanup_lifecycle()
    fail(f"interactive batch authorization interrupted by signal {signum}")


for handled_signal in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
    signal.signal(handled_signal, interrupted)


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
inspection_paths = []
total_bytes = 0
for spec in lane_specs:
    if "=" not in spec:
        fail("lane must be <lane-id>=<lane-manifest>")
    lane_id, manifest_path = spec.split("=", 1)
    if not lane_id or not manifest_path:
        fail("lane must be <lane-id>=<lane-manifest>")
    # Lane artifacts remain caller-owned. This invocation validates and reads
    # them but never infers deletion authority from a caller-selected path.
    expected_inspection_path = manifest_path + ".request.json"
    inspection_paths.append(expected_inspection_path)
    try:
        recorded = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        fail("lane authorization manifest unreadable")
    # The companion path is derived from the manifest path, never trusted from
    # manifest content.
    if recorded.get("schemaVersion") != 2:
        fail("lane authorization manifest schema unsupported")
    if recorded.get("authorizationScope") != "exact-request-envelope-bytes":
        fail("lane authorization manifest scope unsupported")
    digest = recorded.get("requestEnvelopeSha256", "")
    if not isinstance(digest, str) or not HEX64.match(digest):
        fail("lane authorization manifest digest malformed")
    lane_bytes = 0
    count = recorded.get("byteCount")
    if not isinstance(count, int) or count < 0:
        fail("lane authorization manifest byte count malformed")
    lane_bytes += count
    models = recorded.get("modelCandidates")
    provider = recorded.get("providerRouting")
    role_bytes = recorded.get("messageRoleByteCounts")
    inspection_path = recorded.get("inspectionPath")
    if not isinstance(models, list) or not models or not all(
        isinstance(model, str) and model for model in models
    ):
        fail("lane authorization manifest model candidates malformed")
    if not isinstance(provider, dict):
        fail("lane authorization manifest provider routing malformed")
    if not isinstance(role_bytes, list) or not role_bytes or not all(
        isinstance(item, dict)
        and set(item) == {"role", "byteCount"}
        and isinstance(item["role"], str)
        and item["role"]
        and isinstance(item["byteCount"], int)
        and item["byteCount"] >= 0
        for item in role_bytes
    ):
        fail("lane authorization manifest role byte counts malformed")
    if not isinstance(inspection_path, str) or not inspection_path:
        fail("lane authorization manifest inspection path missing")
    if inspection_path != expected_inspection_path or Path(inspection_path).is_symlink():
        fail("lane authorization manifest inspection path is not the owned companion path")
    try:
        inspection_raw = Path(inspection_path).read_bytes()
    except OSError:
        fail("lane request envelope is unavailable for operator inspection")
    if not hmac.compare_digest(hashlib.sha256(inspection_raw).hexdigest(), digest):
        fail("lane request envelope does not match its authorization manifest")
    if digest in digests:
        fail("duplicate lane payload digest")
    digests.append(digest)
    lane_record = {
        "lane_id": lane_id,
        "requestEnvelopeSha256": digest,
        "byteCount": lane_bytes,
        "modelCandidates": models,
        "providerRouting": provider,
        "messageRoleByteCounts": role_bytes,
    }
    lanes.append(lane_record)
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
    if test_failure_stage == "tty-write":
        raise OSError("injected TTY write failure")
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
    for lane, inspection_path in zip(lanes, inspection_paths):
        tty_out.write(
            f"  {lane['lane_id']}  {lane['byteCount']} bytes  "
            f"sha256:{lane['requestEnvelopeSha256']}\n"
        )
        tty_out.write(f"    models: {', '.join(lane['modelCandidates'])}\n")
        tty_out.write(
            "    provider: "
            + json.dumps(lane["providerRouting"], sort_keys=True, separators=(",", ":"))
            + "\n"
        )
        tty_out.write(
            "    message bytes: "
            + ", ".join(
                f"{item['role']}={item['byteCount']}"
                for item in lane["messageRoleByteCounts"]
            )
            + "\n"
        )
        tty_out.write(f"    inspect: {inspection_path}\n")
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
    "schema_version": 2,
    "authorization_mode": "interim_operator_batch",
    "run_id": run_id,
    "operator": operator,
    "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "expires_at": expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "request_envelope_digests": digests,
    "lanes": lanes,
    "scope_note": scope_note,
    "program_sunset": program_sunset,
}

target = Path(batch_path)
if test_failure_stage == "mkdir":
    raise OSError("injected batch directory creation failure")
target.parent.mkdir(parents=True, exist_ok=True)
if test_failure_stage == "mkstemp":
    raise OSError("injected batch temporary-file failure")
handled_signals = (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)
previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, handled_signals)
try:
    temporary_handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", prefix=f".{target.name}.",
        dir=target.parent, delete=False,
    )
    if test_failure_stage == "signal-before-temp-ownership":
        os.kill(os.getpid(), signal.SIGTERM)
    temporary_path = Path(temporary_handle.name)
    os.fchmod(temporary_handle.fileno(), 0o600)
finally:
    signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
try:
    json.dump(document, temporary_handle, sort_keys=True)
    temporary_handle.write("\n")
    temporary_handle.close()
    temporary_handle = None
    # Replacement and rollback-ownership publication are one signal-atomic
    # transition. A pending signal is delivered only after both facts agree.
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, handled_signals)
    try:
        os.replace(temporary_path, target)
        if test_failure_stage == "signal-before-batch-ownership":
            os.kill(os.getpid(), signal.SIGTERM)
        temporary_path = None
        persisted_batch = target
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
except Exception:
    fail("batch authorization could not be persisted")

if test_failure_stage == "final-read":
    raise OSError("injected final batch read failure")
batch_digest = hashlib.sha256(target.read_bytes()).hexdigest()
# Canonical typed validation runs inside the same lifecycle-owning process, so
# no shell handoff can leave an unvalidated batch behind on interruption.
if test_failure_stage == "canonical-validation":
    mutated = json.loads(target.read_text(encoding="utf-8"))
    mutated["unexpected_test_field"] = True
    target.write_text(json.dumps(mutated, sort_keys=True) + "\n", encoding="utf-8")
validation = subprocess.run(
    [
        os.environ["PAYLOAD_AUTH_SELF"], "validate-batch",
        "--batch-file", batch_path, "--run-id", run_id,
    ],
    stdout=subprocess.DEVNULL,
    check=False,
)
if validation.returncode != 0:
    fail("produced batch failed canonical typed validation")
sys.stdout.write(batch_digest + "\n")
sys.stdout.flush()
lifecycle_succeeded = True
PY
  then
    exit 0
  else
    status=$?
    exit "$status"
  fi
fi

if [ "$MODE" = "validate-batch" ]; then
  refuse_when_broker_ready
fi

if [ "$MODE" = "verify-batch" ]; then
  refuse_when_broker_ready
fi

PAYLOAD_AUTH_PROGRAM_SUNSET="$PROGRAM_SUNSET" \
PAYLOAD_AUTH_BATCH_FILE="$BATCH_FILE" \
PAYLOAD_AUTH_RUN_ID="$RUN_ID" \
PAYLOAD_AUTH_LANE_ID="$LANE_ID" \
PAYLOAD_AUTH_REQUEST_FILE="$REQUEST_FILE" \
python3 - "$MODE" "$MANIFEST" "$APPROVED_SHA256" \
  ${CONTENT_FILES[@]+"${CONTENT_FILES[@]}"} <<'PY'
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
    "request_envelope_digests",
    "lanes",
    "scope_note",
    "program_sunset",
}
MAX_LIFETIME_SECONDS = 86400


def fail(message):
    print(f"payload-authorization: {message}", file=sys.stderr)
    raise SystemExit(2)


def summarize_request(raw, inspection_path=None):
    try:
        request = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail("request envelope is not valid UTF-8 JSON")
    if not isinstance(request, dict):
        fail("request envelope must be an object")
    models = request.get("models")
    if models is None and isinstance(request.get("model"), str):
        models = [request["model"]]
    if not isinstance(models, list) or not models or not all(
        isinstance(model, str) and model for model in models
    ):
        fail("request envelope model candidates malformed")
    provider = request.get("provider")
    if not isinstance(provider, dict):
        fail("request envelope provider routing malformed")
    messages = request.get("messages")
    if not isinstance(messages, list) or not messages:
        fail("request envelope messages malformed")
    role_bytes = []
    for message in messages:
        if not isinstance(message, dict) or not isinstance(message.get("role"), str) \
                or not isinstance(message.get("content"), str):
            fail("request envelope message malformed")
        role_bytes.append({
            "role": message["role"],
            "byteCount": len(message["content"].encode("utf-8")),
        })
    summary = {
        "schemaVersion": 2,
        "authorizationScope": "exact-request-envelope-bytes",
        "requestEnvelopeSha256": hashlib.sha256(raw).hexdigest(),
        "byteCount": len(raw),
        "modelCandidates": models,
        "providerRouting": provider,
        "messageRoleByteCounts": role_bytes,
    }
    if inspection_path is not None:
        summary["inspectionPath"] = inspection_path
    return summary


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
        fail("batch authorization timestamps are not well-formed UTC timestamps")


def validate_lane_mapping(lane):
    expected_keys = {
        "lane_id", "requestEnvelopeSha256", "byteCount", "modelCandidates",
        "providerRouting", "messageRoleByteCounts",
    }
    if not isinstance(lane, dict) or set(lane) != expected_keys:
        fail("batch authorization lane mapping malformed")
    lane_id = lane["lane_id"]
    if not isinstance(lane_id, str) or not lane_id:
        fail("batch authorization lane id malformed")
    digest = lane["requestEnvelopeSha256"]
    if not isinstance(digest, str) or not HEX64.match(digest):
        fail("batch authorization lane digest malformed")
    count = lane["byteCount"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        fail("batch authorization lane byte count malformed")
    models = lane["modelCandidates"]
    if not isinstance(models, list) or not models or not all(
        isinstance(model, str) and model for model in models
    ) or len(set(models)) != len(models):
        fail("batch authorization lane model candidates malformed")
    provider = lane["providerRouting"]
    allowed_provider_keys = {
        "require_parameters", "allow_fallbacks", "data_collection", "zdr",
        "order", "sort",
    }
    if not isinstance(provider, dict) or not {
        "require_parameters", "allow_fallbacks",
    }.issubset(provider) or not set(provider).issubset(allowed_provider_keys):
        fail("batch authorization lane provider routing malformed")
    if not isinstance(provider["require_parameters"], bool) \
            or not isinstance(provider["allow_fallbacks"], bool):
        fail("batch authorization lane provider routing malformed")
    if "data_collection" in provider and provider["data_collection"] != "deny":
        fail("batch authorization lane provider routing malformed")
    if "zdr" in provider and not isinstance(provider["zdr"], bool):
        fail("batch authorization lane provider routing malformed")
    if "sort" in provider and (
        not isinstance(provider["sort"], str) or not provider["sort"]
    ):
        fail("batch authorization lane provider routing malformed")
    if "order" in provider and (
        not isinstance(provider["order"], list) or not provider["order"]
        or not all(isinstance(item, str) and item for item in provider["order"])
    ):
        fail("batch authorization lane provider routing malformed")
    role_bytes = lane["messageRoleByteCounts"]
    if not isinstance(role_bytes, list) or not role_bytes or not all(
        isinstance(item, dict)
        and set(item) == {"role", "byteCount"}
        and isinstance(item["role"], str)
        and item["role"]
        and not isinstance(item["byteCount"], bool)
        and isinstance(item["byteCount"], int)
        and item["byteCount"] >= 0
        for item in role_bytes
    ):
        fail("batch authorization lane role byte counts malformed")
    return lane


def validate_batch(raw, expected_run_id, program_sunset):
    try:
        batch = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail("batch authorization unreadable")
    if not isinstance(batch, dict) or set(batch) != BATCH_KEYS:
        fail("batch authorization schema unexpected")
    if batch["schema_version"] != 2:
        fail("batch authorization schema unsupported")
    if batch["authorization_mode"] != "interim_operator_batch":
        fail("batch authorization mode unexpected")
    if not isinstance(batch["operator"], str) or not batch["operator"].strip():
        fail("batch authorization operator missing")
    if not isinstance(batch["scope_note"], str) or not batch["scope_note"].strip():
        fail("batch authorization scope note missing")
    if not isinstance(batch["run_id"], str) or not batch["run_id"]:
        fail("batch authorization run id missing")
    if not hmac.compare_digest(batch["run_id"], expected_run_id):
        fail("batch authorization was issued for a different run")
    if batch["program_sunset"] != program_sunset:
        fail("batch authorization is sunset-mismatched")
    created_at = parse_stamp(batch["created_at"], "created_at")
    expires_at = parse_stamp(batch["expires_at"], "expires_at")
    if expires_at <= created_at:
        fail("batch authorization expiry precedes issuance")
    if expires_at - created_at > timedelta(seconds=MAX_LIFETIME_SECONDS):
        fail("batch authorization lifetime exceeds the 24-hour maximum")
    sunset = datetime.strptime(program_sunset, "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )
    now = datetime.now(timezone.utc)
    if now >= sunset:
        fail("interim operator-batch program sunset has passed")
    if now >= expires_at:
        fail("batch authorization is expired")
    if now < created_at:
        fail("batch authorization is issued in the future")
    digests = batch["request_envelope_digests"]
    if not isinstance(digests, list) or not digests:
        fail("batch authorization carries no request envelope digests")
    for digest in digests:
        if not isinstance(digest, str) or not HEX64.match(digest):
            fail("batch authorization request envelope digest malformed")
    lanes = batch["lanes"]
    if not isinstance(lanes, list) or len(lanes) != len(digests):
        fail("batch authorization lane mapping malformed")
    lane_ids = set()
    mapped_digests = []
    for lane in lanes:
        validate_lane_mapping(lane)
        lane_id = lane["lane_id"]
        if lane_id in lane_ids:
            fail("batch authorization lane id duplicated")
        lane_ids.add(lane_id)
        mapped_digests.append(lane["requestEnvelopeSha256"])
        if lane["requestEnvelopeSha256"] not in digests:
            fail("batch authorization lane digest is not in the approved set")
    if sorted(mapped_digests) != sorted(digests):
        fail("batch authorization lane mapping does not cover the approved digest set")
    return batch, digests, lanes


current = build_manifest()
request_path = os.environ.get("PAYLOAD_AUTH_REQUEST_FILE", "")
if mode in {"snapshot-envelope", "verify-envelope", "verify-batch"}:
    try:
        request_raw = Path(request_path).read_bytes()
    except OSError:
        fail("request file unreadable")
    inspection_path = manifest_path + ".request.json" if mode == "snapshot-envelope" else None
    request_manifest = summarize_request(request_raw, inspection_path)
else:
    request_raw = b""
    request_manifest = None

if mode == "snapshot-envelope":
    target = Path(manifest_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    inspection_target = Path(request_manifest["inspectionPath"])
    if inspection_target.exists() or inspection_target.is_symlink():
        fail("request envelope inspection already exists")
    inspection_fd, inspection_temporary = tempfile.mkstemp(
        prefix=f".{inspection_target.name}.", dir=inspection_target.parent
    )
    try:
        os.fchmod(inspection_fd, 0o600)
        with os.fdopen(inspection_fd, "wb") as inspection_handle:
            inspection_handle.write(request_raw)
        os.replace(inspection_temporary, inspection_target)
    except Exception:
        try:
            os.unlink(inspection_temporary)
        except OSError:
            pass
        raise
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(request_manifest, handle, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, target)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        try:
            inspection_target.unlink()
        except OSError:
            pass
        raise
    print(request_manifest["requestEnvelopeSha256"])
    raise SystemExit(0)

if mode == "verify-envelope":
    try:
        recorded_request = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        fail("authorization manifest unreadable")
    recorded_core = {
        key: value for key, value in recorded_request.items() if key != "inspectionPath"
    }
    if recorded_core != request_manifest:
        fail("request envelope changed after authorization snapshot")
    if not isinstance(approved, str) or not HEX64.match(approved.lower()):
        fail("approved digest malformed")
    if not hmac.compare_digest(
        approved.lower(), request_manifest["requestEnvelopeSha256"]
    ):
        fail("request envelope digest was not approved")
    print(json.dumps({
        "authorizationMode": "exact-digest",
        "authorizationScope": "operator-approved-exact-request-envelope-bytes",
        "requestEnvelopeSha256": request_manifest["requestEnvelopeSha256"],
    }, sort_keys=True))
    raise SystemExit(0)
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

if mode in {"validate-batch", "verify-batch"}:
    batch_path = Path(os.environ["PAYLOAD_AUTH_BATCH_FILE"])
    run_id = os.environ["PAYLOAD_AUTH_RUN_ID"]
    program_sunset = os.environ["PAYLOAD_AUTH_PROGRAM_SUNSET"]
    try:
        raw = batch_path.read_bytes()
    except OSError:
        fail("batch authorization unreadable")
    batch, digests, lanes = validate_batch(raw, run_id, program_sunset)
    if mode == "validate-batch":
        print(json.dumps({
            "authorizationMode": "interim-operator-batch",
            "batchSha256": hashlib.sha256(raw).hexdigest(),
            "runId": batch["run_id"],
            "expiresAt": batch["expires_at"],
            "programSunset": program_sunset,
            "requestEnvelopeDigestCount": len(digests),
        }, sort_keys=True))
        raise SystemExit(0)
    try:
        recorded_request = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        fail("authorization manifest unreadable")
    recorded_core = {key: value for key, value in recorded_request.items() if key != "inspectionPath"}
    if recorded_core != request_manifest:
        fail("request envelope changed after authorization snapshot")
    lane_id = os.environ.get("PAYLOAD_AUTH_LANE_ID", "")
    approved_lane = next((lane for lane in lanes if lane["lane_id"] == lane_id), None)
    if approved_lane is None:
        fail("request envelope lane is not in this run's batch authorization")
    if not hmac.compare_digest(
        approved_lane["requestEnvelopeSha256"], request_manifest["requestEnvelopeSha256"]
    ) or approved_lane["modelCandidates"] != request_manifest["modelCandidates"]:
        fail("request envelope does not match its approved lane and model binding")
    print(json.dumps({
        "authorizationMode": "interim-operator-batch",
        "authorizationScope": "operator-approved-run-batch-exact-request-envelope-bytes",
        "requestEnvelopeSha256": request_manifest["requestEnvelopeSha256"],
        "batchSha256": hashlib.sha256(raw).hexdigest(),
        "runId": batch["run_id"],
        "expiresAt": batch["expires_at"],
        "programSunset": program_sunset,
    }, sort_keys=True))
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
