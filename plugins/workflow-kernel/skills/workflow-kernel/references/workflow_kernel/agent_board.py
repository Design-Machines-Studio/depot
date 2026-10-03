"""Small immutable file-backed message board for trusted local agent sessions."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


SCHEMA = "agent-message-v1"
SCHEMA_V2 = "agent-message-v2"
INTENTS = {"needs_answer", "next_session", "no_response"}
KINDS = {"question", "handoff", "reply", "completion", "correction"}
OUTCOMES = {"verified", "unavailable", "conflict"}
IDENTITY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
MESSAGE_ID = re.compile(r"^[0-9a-f]{32}$")
MAX_BODY = 4000
MAX_LIST = 100
MAX_FILE_BYTES = 65536


class BoardError(ValueError):
    """Invalid board input or unsafe board state."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BoardError("JSON object contains a duplicate field")
        result[key] = value
    return result


def _reject_constant(_value):
    raise BoardError("JSON contains a non-finite number")


def _loads(raw):
    try:
        return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except BoardError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise BoardError("JSON document is invalid or exceeds parser limits") from exc


def _timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        raise BoardError("created_at must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BoardError("created_at must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BoardError("created_at must include a timezone")
    try:
        parsed.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise BoardError("created_at cannot be represented in UTC") from exc
    return value


def _time_key(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _identity(value, field):
    if not isinstance(value, str) or not IDENTITY.fullmatch(value):
        raise BoardError(f"{field} must be a canonical owner/repository identity")
    return value


def _label(value, field, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > 120:
        raise BoardError(f"{field} must be non-empty plain text up to 120 characters")
    return value.strip()


def _references(value):
    if not isinstance(value, list) or len(value) > 10:
        raise BoardError("source_links must be an array with at most 10 entries")
    result = []
    for link in value:
        if not isinstance(link, dict) or set(link) - {"url", "revision"}:
            raise BoardError("each source link must contain only url and optional revision")
        url, revision = link.get("url"), link.get("revision")
        try:
            parts = urlsplit(url) if isinstance(url, str) else None
        except ValueError as exc:
            raise BoardError("source link url must be an HTTP(S) URL") from exc
        if (parts is None or parts.scheme not in {"https", "http"} or not parts.netloc
                or len(url) > 2000):
            raise BoardError("source link url must be an HTTP(S) URL")
        if revision is not None and (not isinstance(revision, str) or not revision.strip() or len(revision) > 200):
            raise BoardError("source link revision must be non-empty plain text up to 200 characters")
        result.append({"url": url, **({"revision": revision} if revision is not None else {})})
    return result


def validate_message(value):
    required = {
        "schema", "id", "source_project", "source_thread", "destination_project",
        "destination_thread", "kind", "body", "source_links", "created_at",
    }
    optional = {"reply_to", "supersedes_id", "source_verifications", "intent"}
    if not isinstance(value, dict) or required - value.keys() or value.keys() - required - optional:
        raise BoardError("message has missing or unknown fields")
    if not isinstance(value["schema"], str) or value["schema"] not in {SCHEMA, SCHEMA_V2} or not isinstance(value["id"], str) or not MESSAGE_ID.fullmatch(value["id"]):
        raise BoardError("message schema or unique id is invalid")
    if not isinstance(value["kind"], str) or value["kind"] not in KINDS:
        raise BoardError("kind must be question, handoff, reply, completion or correction")
    if value["schema"] == SCHEMA and value["kind"] not in {"question", "handoff", "reply"}:
        raise BoardError("completion and correction require agent-message-v2")
    if value["schema"] == SCHEMA_V2 and "intent" not in value:
        raise BoardError("agent-message-v2 requires explicit intent")
    if "intent" in value and (not isinstance(value["intent"], str) or value["intent"] not in INTENTS):
        raise BoardError("intent must be needs_answer, next_session or no_response")
    body = value["body"]
    if not isinstance(body, str) or not body.strip() or len(body) > (1200 if value["schema"] == SCHEMA_V2 else MAX_BODY):
        raise BoardError("body must be concise non-empty plain text (v2: 1200; v1: 4000 characters)")
    if any(ord(char) < 32 and char not in "\n\t\r" for char in body):
        raise BoardError("body contains non-text control characters")
    try:
        body.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise BoardError("body must be valid Unicode text") from exc
    result = {
        "schema": value["schema"],
        "id": value["id"],
        "source_project": _identity(value["source_project"], "source_project"),
        "source_thread": _label(value["source_thread"], "source_thread"),
        "destination_project": _identity(value["destination_project"], "destination_project"),
        "destination_thread": _label(value["destination_thread"], "destination_thread", optional=True),
        "kind": value["kind"],
        "body": body.strip(),
        "source_links": _references(value["source_links"]),
        "created_at": _timestamp(value["created_at"]),
    }
    if "intent" in value:
        result["intent"] = value["intent"]
    for field in ("reply_to", "supersedes_id"):
        ref = value.get(field)
        if ref is not None:
            if not isinstance(ref, str) or not MESSAGE_ID.fullmatch(ref) or ref == value["id"]:
                raise BoardError(f"{field} must identify another message")
            result[field] = ref
    if value["kind"] in {"reply", "completion"} and "reply_to" not in result:
        raise BoardError("reply and completion messages require reply_to")
    if value["kind"] not in {"reply", "completion"} and "reply_to" in result:
        raise BoardError("only reply or completion messages may use reply_to")
    if value["kind"] == "correction" and "supersedes_id" not in result:
        raise BoardError("correction requires supersedes_id")
    if "source_verifications" in value:
        if value["kind"] not in {"reply", "completion"}:
            raise BoardError("source verifications belong on a reply that performed the check")
        checks = value["source_verifications"]
        if not isinstance(checks, list) or len(checks) > 10:
            raise BoardError("source_verifications must be an array with at most 10 entries")
        result["source_verifications"] = []
        for check in checks:
            if not isinstance(check, dict) or set(check) != {"url", "revision", "checked_at", "outcome"}:
                raise BoardError("each source verification needs url, revision, checked_at and outcome")
            if not isinstance(check["outcome"], str) or check["outcome"] not in OUTCOMES:
                raise BoardError("source verification outcome must be verified, unavailable or conflict")
            checked = _timestamp(check["checked_at"])
            if not any(link["url"] == check["url"] and link.get("revision") == check["revision"]
                       for link in result["source_links"]):
                raise BoardError("source verification must match a cited source link and revision")
            result["source_verifications"].append({**check, "checked_at": checked})
    return result


def _root(directory):
    try:
        root = Path(directory).resolve(strict=True)
    except (OSError, TypeError) as exc:
        raise BoardError("configured board directory does not exist; reads never create it") from exc
    if not root.is_dir():
        raise BoardError("configured board path is not a directory")
    return root


def _read_files(root):
    messages, diagnostics = {}, []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.suffix != ".json":
            continue
        try:
            if path.is_symlink() or not path.is_file() or path.name != f"{path.stem}.json" or not MESSAGE_ID.fullmatch(path.stem):
                raise BoardError("unsafe or invalid message filename")
            if path.stat().st_size > MAX_FILE_BYTES:
                raise BoardError("message file exceeds the 65536-byte limit")
            value = _loads(path.read_text(encoding="utf-8"))
            message = validate_message(value)
            if path.stem != message["id"]:
                raise BoardError("filename does not match message id")
            messages[message["id"]] = message
        except (OSError, UnicodeError, json.JSONDecodeError, RecursionError, ValueError, BoardError) as exc:
            diagnostics.append({"file": path.name, "error": str(exc) or type(exc).__name__})
    # Imported history is untrusted relationship evidence too. Remove broken
    # edges transitively; matching labels never repair a missing explicit edge.
    while True:
        invalid = []
        for message in messages.values():
            try:
                _validate_relationships(message, messages)
            except BoardError as exc:
                invalid.append(message["id"])
                diagnostics.append({"file": message["id"] + ".json", "error": str(exc)})
        if not invalid:
            break
        for message_id in invalid:
            del messages[message_id]
    return messages, diagnostics


def _validate_relationships(value, messages):
    ancestors = [value.get(field) for field in ("reply_to", "supersedes_id") if value.get(field)]
    seen = set()
    while ancestors:
        ancestor = ancestors.pop()
        if ancestor == value["id"]:
            raise BoardError("message relationships contain a cycle")
        if ancestor in seen or ancestor not in messages:
            continue
        seen.add(ancestor)
        ancestors.extend(messages[ancestor].get(field) for field in ("reply_to", "supersedes_id")
                         if messages[ancestor].get(field))
    for field in ("reply_to", "supersedes_id"):
        if field in value and value[field] not in messages:
            raise BoardError(f"{field} does not reference a readable existing message")
    if "reply_to" in value:
        parent = messages[value["reply_to"]]
        reciprocal = (value["source_project"] == parent["destination_project"]
                      and value["destination_project"] == parent["source_project"])
        sender_update = (value["kind"] == "completion"
                         and value["source_project"] == parent["source_project"]
                         and value["destination_project"] == parent["destination_project"]
                         and value["destination_thread"] == parent["destination_thread"])
        if not (reciprocal or sender_update):
            raise BoardError("reply source and destination must reciprocate the referenced message")
    if "supersedes_id" in value:
        prior = messages[value["supersedes_id"]]
        if (value["source_project"] != prior["source_project"]
                or value["destination_project"] != prior["destination_project"]
                or value["destination_thread"] != prior["destination_thread"]):
            raise BoardError("superseding message must retain the original source and destination")


def post(directory, message):
    root = _root(directory)
    value = validate_message(message)
    messages, _ = _read_files(root)
    _validate_relationships(value, messages)
    final_path = root / f"{value['id']}.json"
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=".agent-message-", suffix=".tmp", dir=root)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # Same-directory hard-link publication is atomic and cannot replace an
        # existing ID. A simultaneous writer with that ID loses cleanly.
        os.link(temporary, final_path)
    except FileExistsError as exc:
        raise BoardError("duplicate message id; existing message was preserved") from exc
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return value


def intent(message):
    """Historical handoffs are context, never retroactive answer obligations."""
    return message.get("intent", {"question": "needs_answer", "handoff": "next_session"}.get(
        message["kind"], "no_response"))


def _state(message, messages):
    if any(item.get("supersedes_id") == message["id"] for item in messages.values()):
        return "superseded"
    # Completion updates are outcome claims, never recipient-answer evidence.
    if any(item.get("reply_to") == message["id"]
           and item["kind"] == "reply"
           and item["source_project"] == message["destination_project"]
           for item in messages.values()):
        return "answered"
    if intent(message) == "needs_answer":
        return "unanswered"
    return "informational"


def _exchange_id(message, messages):
    seen = set()
    while message["id"] not in seen:
        seen.add(message["id"])
        parent = message.get("supersedes_id") or message.get("reply_to")
        if parent not in messages:
            return message["id"]
        message = messages[parent]
    return min(seen)  # Defensive bound for manually imported cyclic history.


def list_messages(directory, destination_project=None, *, destination_thread=None,
                  limit=20, offset=0, actionable=False, now=None):
    root = _root(directory)
    project = _identity(destination_project, "destination_project") if destination_project is not None else None
    if project is None and not actionable:
        raise BoardError("destination_project is required outside the operator inbox")
    if type(limit) is not int or not 1 <= limit <= MAX_LIST:
        raise BoardError(f"limit must be between 1 and {MAX_LIST}")
    if type(offset) is not int or offset < 0:
        raise BoardError("offset must be a non-negative integer")
    thread = _label(destination_thread, "destination_thread") if destination_thread is not None else None
    messages, diagnostics = _read_files(root)
    relevant = [item for item in messages.values()
                if (project is None or item["destination_project"] == project)
                and (thread is None or item["destination_thread"] == thread)
                and (not actionable or _state(item, messages) == "unanswered")]
    relevant.sort(key=lambda item: (_time_key(item["created_at"]), item["id"]), reverse=True)
    selected = relevant[offset:offset + limit]
    instant = now or datetime.now(timezone.utc)
    rows = []
    for item in selected:
        exchange = _exchange_id(item, messages)
        related = [other for other in messages.values()
                   if other["id"] != item["id"]
                   and (other["kind"] in {"reply", "completion"} or "supersedes_id" in other)
                   and _exchange_id(other, messages) == exchange]
        related.sort(key=lambda other: (_time_key(other["created_at"]), other["id"]))
        latest = related[-1] if related else None
        rows.append({key: item[key] for key in (
            "id", "kind", "source_project", "source_thread", "destination_project",
            "destination_thread", "created_at", "source_links")})
        rows[-1].update(body=item["body"].splitlines()[0][:240], intent=intent(item),
                        state=_state(item, messages), exchange_id=exchange,
                        age_seconds=max(0, int((instant - _time_key(item["created_at"])).total_seconds())),
                        latest_update=({"id": latest["id"], "kind": latest["kind"],
                                        "created_at": latest["created_at"],
                                        "body": latest["body"].splitlines()[0][:240],
                                        "source_links": latest["source_links"]} if latest else None),
                        message_path=str(root / (item["id"] + ".json")),
                        delivery=delivery_status(root, item["id"]))
    return {
        "messages": rows, "returned": len(selected), "more": len(relevant) > offset + limit,
        "next_offset": offset + len(selected) if len(relevant) > offset + limit else None,
        "matching_count": len(relevant), "diagnostics": diagnostics[:20],
        "diagnostics_more": len(diagnostics) > 20,
    }


def read_message(directory, message_id):
    root = _root(directory)
    if not isinstance(message_id, str) or not MESSAGE_ID.fullmatch(message_id):
        raise BoardError("message id is invalid")
    messages, diagnostics = _read_files(root)
    if message_id not in messages:
        if any(item["file"] == f"{message_id}.json" for item in diagnostics):
            raise BoardError(f"message is malformed; inspect diagnostics: {diagnostics}")
        raise BoardError("message id was not found")
    message = messages[message_id]
    replies = [item for item in messages.values() if item.get("reply_to") == message_id]
    superseders = [item for item in messages.values() if item.get("supersedes_id") == message_id]
    replies.sort(key=lambda item: (_time_key(item["created_at"]), item["id"]))
    superseders.sort(key=lambda item: (_time_key(item["created_at"]), item["id"]))
    return {"message": message, "state": _state(message, messages),
            "intent": intent(message), "exchange_id": _exchange_id(message, messages),
            "delivery": delivery_status(root, message_id),
            "replies": replies, "superseded_by": superseders,
            "diagnostics": diagnostics[:20], "diagnostics_more": len(diagnostics) > 20}


def delivery_status(root, message_id):
    """Queue acceptance is not proof of session delivery or recipient reading."""
    receipt = root / ".delivery" / message_id
    result = {"posted": True, "notification_attempted": False,
              "queue_accepted": False, "delivered": "unknown", "read": "unknown",
              "fallback": "check_inbox_at_start_resume_or_dependency_checkpoint"}
    if receipt.is_dir() and not receipt.is_symlink():
        result["notification_attempted"] = (receipt / "attempt.json").is_file()
        outcome = receipt / "outcome.json"
        try:
            if outcome.is_symlink() or outcome.stat().st_size > MAX_FILE_BYTES:
                return result
            saved = _loads(outcome.read_text(encoding="utf-8"))
            if (isinstance(saved, dict) and isinstance(saved.get("status"), str)
                    and saved["status"] in {"queue_accepted", "failed", "unavailable"}):
                result["notification_status"] = saved["status"]
                result["queue_accepted"] = saved["status"] == "queue_accepted"
        except (OSError, ValueError):
            pass
    return result


def _binding(path, message, now):
    import stat
    import uuid

    candidate = Path(path)
    try:
        info = candidate.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_nlink != 1 or info.st_size > MAX_FILE_BYTES):
            raise BoardError("binding must be an operator-owned single-link mode-0600 regular file")
        # Routing authority cannot come from message bodies or a product checkout.
        for parent in candidate.resolve().parents:
            if (parent / ".git").exists():
                raise BoardError("session binding must be outside every Git checkout")
        value = _loads(candidate.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BoardError("session binding is unavailable") from exc
    fields = {"schema", "issuer", "host", "session_id", "destination_project",
              "destination_thread", "verified_at", "expires_at", "evidence", "executable"}
    if not isinstance(value, dict) or set(value) != fields:
        raise BoardError("session binding has missing or unknown fields")
    if value["schema"] != "agent-session-binding-v1" or value["issuer"] != "operator_verified":
        raise BoardError("routing requires a host/operator-verified session binding")
    if not isinstance(value["host"], str) or value["host"] not in {"codex", "claude"}:
        raise BoardError("unsupported notification host")
    try:
        if str(uuid.UUID(value["session_id"])) != value["session_id"]:
            raise ValueError()
    except (ValueError, TypeError, AttributeError) as exc:
        raise BoardError("binding requires an exact canonical session UUID") from exc
    _identity(value["destination_project"], "destination_project")
    _label(value["destination_thread"], "destination_thread", optional=True)
    if (value["destination_project"] != message["destination_project"]
            or value["destination_thread"] != message["destination_thread"]):
        raise BoardError("binding does not match this exact destination and thread")
    verified = _time_key(_timestamp(value["verified_at"]))
    expires = _time_key(_timestamp(value["expires_at"]))
    if verified > now or expires <= now or not 0 < (expires - verified).total_seconds() <= 28800:
        raise BoardError("session binding has expired or exceeds eight hours; operator must verify it again")
    _label(value["evidence"], "evidence")
    if not isinstance(value["executable"], str) or not Path(value["executable"]).is_absolute():
        raise BoardError("binding executable must be an absolute trusted CLI path")
    return value


def _write_delivery(path, value):
    with path.open("x", encoding="utf-8") as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(value, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def notify(directory, message_id, binding_path, *, now=None):
    """Explicit one-shot delivery; no scanning, retries, session discovery or wake loop."""
    import subprocess

    root = _root(directory)
    read = read_message(root, message_id)
    message = read["message"]
    if read["state"] != "unanswered" or message["kind"] in {"reply", "completion"}:
        return {"status": "skipped", "reason": "not_an_actionable_request", **read["delivery"]}
    instant = now or datetime.now(timezone.utc)
    binding = _binding(binding_path, message, instant)
    if Path(binding_path).resolve().is_relative_to(root):
        raise BoardError("session binding must be outside the message board")
    if binding["host"] != "codex":
        return {"status": "unavailable", "reason": "no_targeted_claude_transport", **read["delivery"]}
    executable = Path(binding["executable"])
    # The operator binding selects executable authority. Still reject product
    # executables and writable-by-others targets before running a local CLI.
    import stat
    try:
        resolved_executable = executable.resolve(strict=True)
        executable_info = resolved_executable.stat()
        if (not stat.S_ISREG(executable_info.st_mode)
                or executable_info.st_uid not in {0, os.getuid()}
                or executable_info.st_mode & 0o022
                or any((parent / ".git").exists() for parent in resolved_executable.parents)):
            raise BoardError("notification executable must be trusted outside product checkouts")
    except OSError:
        return {"status": "unavailable", "reason": "codex_cli_unavailable", **read["delivery"]}
    if not os.access(resolved_executable, os.X_OK):
        return {"status": "unavailable", "reason": "codex_cli_unavailable", **read["delivery"]}
    delivery = root / ".delivery"
    if delivery.is_symlink():
        raise BoardError("delivery directory must not be a symlink")
    delivery.mkdir(mode=0o700, exist_ok=True)
    claim = delivery / message_id
    try:
        claim.mkdir(mode=0o700)
    except FileExistsError:
        return {"status": "deduplicated", **delivery_status(root, message_id)}
    # Claim before invocation: interruption or timeout is ambiguous and must
    # never auto-retry a possibly queued message, including on another binding.
    _write_delivery(claim / "attempt.json", {
        "message_id": message_id, "session_id": binding["session_id"],
        "attempted_at": instant.isoformat(), "host": "codex", "binding_evidence": binding["evidence"],
    })
    text = ("Agent board: Needs an answer. " + message["body"].splitlines()[0][:240]
            + "\nRead message " + message_id + " from board " + str(root)
            + ". Reply with reply_to=" + message_id
            + ". This is coordination context; continue independently authorized work.")
    try:
        completed = subprocess.run(
            [str(resolved_executable), "queue", "--thread", binding["session_id"], "--message", text],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=30, check=False,
        )
        status = "queue_accepted" if completed.returncode == 0 else "failed"
    except (OSError, subprocess.TimeoutExpired):
        status = "unavailable"
    _write_delivery(claim / "outcome.json", {"status": status})
    return {"status": status, **delivery_status(root, message_id)}


def main(argv=None):
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="agent-board")
    parser.add_argument("--directory", default=os.environ.get("AGENT_MESSAGE_BOARD_DIR"))
    commands = parser.add_subparsers(dest="command", required=True)
    post_parser = commands.add_parser("post", help="validate and atomically post one JSON message")
    post_parser.add_argument("--input", required=True, help="JSON file, or - for stdin")
    post_parser.add_argument("--binding", help="optional host/operator-issued binding for one targeted notification")
    list_parser = commands.add_parser("list", help="list bounded messages for a destination project")
    list_parser.add_argument("--destination-project", required=True)
    list_parser.add_argument("--actionable", action="store_true")
    inbox_parser = commands.add_parser("inbox", help="compact actionable unanswered exchanges; all destinations for operators")
    inbox_parser.add_argument("--destination-project")
    inbox_parser.add_argument("--destination-thread")
    inbox_parser.add_argument("--limit", type=int, default=20)
    inbox_parser.add_argument("--offset", type=int, default=0)
    notify_parser = commands.add_parser("notify", help="target one actionable message using a host/operator-issued binding")
    notify_parser.add_argument("message_id")
    notify_parser.add_argument("--binding", required=True)
    list_parser.add_argument("--destination-thread")
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--offset", type=int, default=0)
    read_parser = commands.add_parser("read", help="read one message, replies and superseding messages")
    read_parser.add_argument("message_id")
    args = parser.parse_args(argv)
    if not args.directory:
        raise BoardError("set AGENT_MESSAGE_BOARD_DIR or pass --directory")
    if args.command == "post":
        text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
        result = post(args.directory, _loads(text))
        if args.binding:
            # Message publication remains durable even when routing is unavailable.
            try:
                notification = notify(args.directory, result["id"], args.binding)
            except BoardError as exc:
                notification = {"status": "unavailable", "reason": str(exc),
                                **delivery_status(_root(args.directory), result["id"])}
            result = {"message": result, "notification": notification}
    elif args.command in {"list", "inbox"}:
        result = list_messages(args.directory, args.destination_project,
                               destination_thread=args.destination_thread, limit=args.limit,
                               offset=args.offset, actionable=args.command == "inbox" or args.actionable)
    elif args.command == "notify":
        result = notify(args.directory, args.message_id, args.binding)
    else:
        result = read_message(args.directory, args.message_id)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0
