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
KINDS = {"question", "handoff", "reply"}
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
    return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)


def _timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        raise BoardError("created_at must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BoardError("created_at must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BoardError("created_at must include a timezone")
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
    optional = {"reply_to", "supersedes_id", "source_verifications"}
    if not isinstance(value, dict) or required - value.keys() or value.keys() - required - optional:
        raise BoardError("message has missing or unknown fields")
    if value["schema"] != SCHEMA or not isinstance(value["id"], str) or not MESSAGE_ID.fullmatch(value["id"]):
        raise BoardError("message schema or unique id is invalid")
    if not isinstance(value["kind"], str) or value["kind"] not in KINDS:
        raise BoardError("kind must be question, handoff or reply")
    body = value["body"]
    if not isinstance(body, str) or not body.strip() or len(body) > MAX_BODY:
        raise BoardError("body must be concise non-empty plain text up to 4000 characters")
    if any(ord(char) < 32 and char not in "\n\t\r" for char in body):
        raise BoardError("body contains non-text control characters")
    try:
        body.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise BoardError("body must be valid Unicode text") from exc
    result = {
        "schema": SCHEMA,
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
    for field in ("reply_to", "supersedes_id"):
        ref = value.get(field)
        if ref is not None:
            if not isinstance(ref, str) or not MESSAGE_ID.fullmatch(ref) or ref == value["id"]:
                raise BoardError(f"{field} must identify another message")
            result[field] = ref
    if value["kind"] == "reply" and "reply_to" not in result:
        raise BoardError("reply messages require reply_to")
    if value["kind"] != "reply" and "reply_to" in result:
        raise BoardError("only reply messages may use reply_to")
    if "source_verifications" in value:
        if value["kind"] != "reply":
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
    return messages, diagnostics


def post(directory, message):
    root = _root(directory)
    value = validate_message(message)
    messages, _ = _read_files(root)
    for field in ("reply_to", "supersedes_id"):
        if field in value and value[field] not in messages:
            raise BoardError(f"{field} does not reference a readable existing message")
    if "reply_to" in value:
        parent = messages[value["reply_to"]]
        if (value["source_project"] != parent["destination_project"]
                or value["destination_project"] != parent["source_project"]):
            raise BoardError("reply source and destination must reciprocate the referenced message")
    if "supersedes_id" in value:
        prior = messages[value["supersedes_id"]]
        if value["destination_project"] != prior["destination_project"]:
            raise BoardError("superseding message must retain the original destination project")
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


def _state(message, messages):
    if any(item.get("supersedes_id") == message["id"] for item in messages.values()):
        return "superseded"
    if message["kind"] in {"question", "handoff"}:
        return "answered" if any(item.get("reply_to") == message["id"] for item in messages.values()) else "unanswered"
    return "reply"


def list_messages(directory, destination_project, *, destination_thread=None, limit=20, offset=0):
    root = _root(directory)
    project = _identity(destination_project, "destination_project")
    if type(limit) is not int or not 1 <= limit <= MAX_LIST:
        raise BoardError(f"limit must be between 1 and {MAX_LIST}")
    if type(offset) is not int or offset < 0:
        raise BoardError("offset must be a non-negative integer")
    thread = _label(destination_thread, "destination_thread") if destination_thread is not None else None
    messages, diagnostics = _read_files(root)
    relevant = [item for item in messages.values()
                if item["destination_project"] == project
                and (thread is None or item["destination_thread"] == thread)]
    relevant.sort(key=lambda item: (_time_key(item["created_at"]), item["id"]), reverse=True)
    selected = relevant[offset:offset + limit]
    return {
        "messages": [{"id": item["id"], "kind": item["kind"], "source_project": item["source_project"],
                      "source_thread": item["source_thread"], "destination_project": item["destination_project"],
                      "destination_thread": item["destination_thread"], "body": item["body"],
                      "created_at": item["created_at"], "state": _state(item, messages)} for item in selected],
        "returned": len(selected), "more": len(relevant) > offset + limit,
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
            "replies": replies, "superseded_by": superseders,
            "diagnostics": diagnostics[:20], "diagnostics_more": len(diagnostics) > 20}


def main(argv=None):
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="agent-board")
    parser.add_argument("--directory", default=os.environ.get("AGENT_MESSAGE_BOARD_DIR"))
    commands = parser.add_subparsers(dest="command", required=True)
    post_parser = commands.add_parser("post", help="validate and atomically post one JSON message")
    post_parser.add_argument("--input", required=True, help="JSON file, or - for stdin")
    list_parser = commands.add_parser("list", help="list bounded messages for a destination project")
    list_parser.add_argument("--destination-project", required=True)
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
    elif args.command == "list":
        result = list_messages(args.directory, args.destination_project,
                               destination_thread=args.destination_thread, limit=args.limit,
                               offset=args.offset)
    else:
        result = read_message(args.directory, args.message_id)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0
