"""Bounded observation metadata. Independent of workflow state and receipts.

POSIX local filesystems only; the configured private parent is a trust boundary.
All descendants are accessed through pinned, no-follow directory descriptors.
"""
from __future__ import annotations

import copy
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import stat
import time
import uuid
from contextlib import contextmanager

CONTRACT = "live-observation-v1"
MAX_BYTES = 65536
MAX_INPUT = 262144
MAX_ACTIVITY = 200
MAX_SESSIONS = 200
ACTIVITIES = ("session_started", "session_resumed", "session_closed", "turn_submitted",
              "tool_started", "tool_returned", "approval_requested", "compaction_started",
              "compaction_finished", "agent_started", "response_closed", "interrupted",
              "outcome_reported")
REASONS = ("not_reported", "unsupported_by_source", "parent_model_not_child_model",
           "explicit_binding_required")
IDENTITIES = ("session", "turn", "agent", "parent", "attempt", "work", "event",
              "tool_call", "trigger_turn", "fork_parent")
FACTS = IDENTITIES + ("model", "source_timestamp")
CODES = ("activity_truncated", "session_limit", "invalid_input", "publication_failed",
         "writer_busy", "identity_conflict", "snapshot_limit")
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")


class LiveObservationError(ValueError):
    """Errors never retain rejected values, parser details or paths."""
    def __init__(self, code="invalid_input"):
        self.code = code if code in CODES else "invalid_input"
        super().__init__(self.code)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode()


def digest(value):
    return "sha256:" + hashlib.sha256(encode(value)).hexdigest()


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds")


def timestamp(value):
    if type(value) is not str or len(value) > 40:
        raise LiveObservationError()
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed
    except ValueError:
        raise LiveObservationError() from None


def token(value):
    if type(value) is not str or not TOKEN.fullmatch(value):
        raise LiveObservationError()
    return value


def closed(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise LiveObservationError()


def parse_bounded(raw, limit=MAX_INPUT):
    if type(raw) is not bytes or len(raw) > limit:
        raise LiveObservationError()
    # Reject deeply nested data before the JSON decoder allocates it.
    depth = 0
    quoted = escaped = False
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == 92:
                escaped = True
            elif char == 34:
                quoted = False
        elif char == 34:
            quoted = True
        elif char in (91, 123):
            depth += 1
            if depth > 12:
                raise LiveObservationError()
        elif char in (93, 125):
            depth -= 1
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise LiveObservationError()
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(LiveObservationError()))
    except (ValueError, UnicodeError, RecursionError):
        raise LiveObservationError() from None
    if type(value) is not dict:
        raise LiveObservationError()
    return value


def available(value, provenance="native_callback"):
    return {"value": value, "reason": None, "provenance": provenance}


def unavailable(reason="not_reported"):
    return {"value": None, "reason": reason, "provenance": None}


def validate_event(value):
    closed(value, ("contract", "workspace", "producer", "publication_id", "observed_at",
                   "activity", "facts", "execution", "response", "session_state", "attention",
                   "outcome"))
    if value["contract"] != CONTRACT:
        raise LiveObservationError()
    for key in ("workspace", "producer", "publication_id"):
        token(value[key])
    timestamp(value["observed_at"])
    if value["activity"] not in ACTIVITIES:
        raise LiveObservationError()
    closed(value["facts"], FACTS)
    for key, fact in value["facts"].items():
        closed(fact, ("value", "reason", "provenance"))
        if fact["value"] is None:
            if fact["reason"] not in REASONS or fact["provenance"] is not None:
                raise LiveObservationError()
        else:
            if fact["reason"] is not None or fact["provenance"] not in ("native_callback", "explicit_binding"):
                raise LiveObservationError()
            (timestamp if key == "source_timestamp" else token)(fact["value"])
    if value["facts"]["session"]["value"] is None:
        raise LiveObservationError()
    for key, choices in {
        "execution": ("unknown", "active", "waiting", "interrupted", "idle"),
        "response": ("unknown", "open", "closed"),
        "session_state": ("unknown", "open", "closed"),
        "attention": ("unknown", "none", "approval_required"),
        "outcome": ("unknown", "success", "failure"),
    }.items():
        if value[key] not in choices:
            raise LiveObservationError()
    if value["outcome"] != "unknown" and value["activity"] != "outcome_reported":
        raise LiveObservationError()
    if len(encode(value)) > 8192:
        raise LiveObservationError()
    return value


def session_key(event):
    return hashlib.sha256(encode([event["workspace"], event["producer"],
                                 event["facts"]["session"]["value"]])).hexdigest()


def validate_live_observation(value):
    """Validate a public snapshot, including its bounded history and digest."""
    closed(value, ("contract", "workspace", "producer", "session_key", "revision",
                   "published_at", "last_observed_at", "recent_activity", "dropped_activity",
                   "diagnostics", "state", "relationships", "last_observation", "digest"))
    if value["contract"] != CONTRACT:
        raise LiveObservationError()
    for key in ("workspace", "producer", "session_key"):
        token(value[key])
    if type(value["revision"]) is not int or not 1 <= value["revision"] <= 2**53 - 1:
        raise LiveObservationError()
    if type(value["dropped_activity"]) is not int or not 0 <= value["dropped_activity"] < 2**53:
        raise LiveObservationError()
    timestamp(value["published_at"])
    timestamp(value["last_observed_at"])
    events = value["recent_activity"]
    if type(events) is not list or not 1 <= len(events) <= MAX_ACTIVITY:
        raise LiveObservationError()
    closed(value["state"], ("execution", "response", "session_state", "attention", "outcome"))
    closed(value["relationships"], ("parent", "fork_parent", "work"))
    for field, fact in value["state"].items():
        closed(fact, ("value", "observed_at"))
        timestamp(fact["observed_at"])
        choices = {"execution": ("unknown", "active", "waiting", "interrupted", "idle"),
                   "response": ("unknown", "open", "closed"),
                   "session_state": ("unknown", "open", "closed"),
                   "attention": ("unknown", "none", "approval_required"),
                   "outcome": ("unknown", "success", "failure")}
        if fact["value"] not in choices[field]:
            raise LiveObservationError()
    for related in value["relationships"].values():
        if related is not None:
            token(related)
    ids = set()
    for event in events:
        validate_event(event)
        if (event["workspace"] != value["workspace"] or event["producer"] != value["producer"]
                or session_key(event) != value["session_key"] or event["publication_id"] in ids):
            raise LiveObservationError("identity_conflict")
        ids.add(event["publication_id"])
    latest = validate_event(value["last_observation"])
    if session_key(latest) != value["session_key"] or latest["workspace"] != value["workspace"] or latest["producer"] != value["producer"]:
        raise LiveObservationError()
    if value["last_observed_at"] != latest["observed_at"] or any(timestamp(e["observed_at"]) > timestamp(latest["observed_at"]) for e in events):
        raise LiveObservationError()
    if value["diagnostics"] != (["activity_truncated"] if value["dropped_activity"] else []):
        raise LiveObservationError()
    if value["digest"] != digest({k: v for k, v in value.items() if k != "digest"}):
        raise LiveObservationError()
    if len(encode(value)) > MAX_BYTES:
        raise LiveObservationError("snapshot_limit")
    return value


def reduce_live_observation(previous, event, published_at=None):
    """Append observation order, never claiming native causal ordering.

    Repeated observer IDs are idempotent inside retained history. Native IDs
    never deduplicate distinct observer deliveries. Older replay is unsupported.
    """
    validate_event(event)
    event = copy.deepcopy(event)
    if previous is not None:
        validate_live_observation(previous)
        if (previous["session_key"] != session_key(event)
                or previous["workspace"] != event["workspace"] or previous["producer"] != event["producer"]):
            raise LiveObservationError("identity_conflict")
        for old in previous["recent_activity"]:
            if old["publication_id"] == event["publication_id"]:
                if old != event:
                    raise LiveObservationError("identity_conflict")
                return copy.deepcopy(previous)
            for key in ("parent", "fork_parent", "work"):
                a, b = old["facts"][key]["value"], event["facts"][key]["value"]
                if a is not None and b is not None and a != b:
                    raise LiveObservationError("identity_conflict")
    relationships = copy.deepcopy(previous["relationships"]) if previous else dict.fromkeys(("parent", "fork_parent", "work"))
    for key in relationships:
        incoming = event["facts"][key]["value"]
        if incoming is not None:
            if relationships[key] not in (None, incoming):
                raise LiveObservationError("identity_conflict")
            relationships[key] = incoming
    state = copy.deepcopy(previous["state"]) if previous else {}
    for key in ("execution", "response", "session_state", "attention", "outcome"):
        if key not in state or (event[key] != "unknown" and (state[key]["value"] == "unknown" or timestamp(event["observed_at"]) >= timestamp(state[key]["observed_at"]))):
            state[key] = {"value": event[key], "observed_at": event["observed_at"]}
    latest = event
    if previous and timestamp(previous["last_observed_at"]) > timestamp(event["observed_at"]):
        latest = previous["last_observation"]
    result = {
        "last_observation": copy.deepcopy(latest),
        "state": state, "relationships": relationships,
        "contract": CONTRACT, "workspace": event["workspace"], "producer": event["producer"],
        "session_key": session_key(event), "revision": previous["revision"] + 1 if previous else 1,
        "published_at": published_at or stamp(), "last_observed_at": latest["observed_at"],
        "recent_activity": copy.deepcopy(previous["recent_activity"]) + [event] if previous else [event],
        "dropped_activity": previous["dropped_activity"] if previous else 0, "diagnostics": [],
    }
    while True:
        result["diagnostics"] = ["activity_truncated"] if result["dropped_activity"] else []
        result["digest"] = digest({k: v for k, v in result.items() if k != "digest"})
        if len(result["recent_activity"]) <= MAX_ACTIVITY and len(encode(result)) <= MAX_BYTES:
            break
        if len(result["recent_activity"]) == 1:
            raise LiveObservationError("snapshot_limit")
        result["recent_activity"].pop(0)
        result["dropped_activity"] += 1
    return validate_live_observation(result)


def observation_view(snapshot, now=None, read_health="ok"):
    """Reader projection: silence and read failure never change recorded state."""
    validate_live_observation(snapshot)
    if read_health not in ("ok", "failed"):
        raise LiveObservationError()
    latest = snapshot["last_observation"]
    age = ((now or dt.datetime.now(dt.timezone.utc)) - timestamp(snapshot["last_observed_at"])).total_seconds()
    return {"last_activity": latest["activity"],
            **{k: v["value"] for k, v in snapshot["state"].items()},
            "contact": "confirmed" if 0 <= age <= 30 and read_health == "ok" else "unconfirmed",
            "producer_health": "last_publication_valid", "read_health": read_health,
            "ordering": "observation_order_only"}


@contextmanager
def pinned_directory(path):
    path = os.fspath(path)
    if not path.startswith("/") or any(p in ("", ".", "..") for p in path.split("/")[1:]):
        raise LiveObservationError("publication_failed")
    fds = [os.open("/", os.O_RDONLY | os.O_DIRECTORY)]
    names = path.split("/")[1:]
    try:
        for name in names:
            fds.append(os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fds[-1]))
        def verify():
            for parent, child, name in zip(fds, fds[1:], names):
                a, b = os.stat(name, dir_fd=parent, follow_symlinks=False), os.fstat(child)
                if (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino) or not stat.S_ISDIR(a.st_mode):
                    raise LiveObservationError("publication_failed")
        verify()
        yield fds[-1], verify
    finally:
        for fd in reversed(fds):
            os.close(fd)


def private_file(fd):
    s = os.fstat(fd)
    if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_uid != os.getuid() or s.st_mode & 0o077:
        raise LiveObservationError("publication_failed")
    return s


def read_snapshot(fd, name="snapshot.json"):
    try:
        source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    except FileNotFoundError:
        return None
    try:
        before = private_file(source)
        raw = os.read(source, MAX_BYTES + 1)
        after = private_file(source)
        linked = os.stat(name, dir_fd=fd, follow_symlinks=False)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if identity(before) != identity(after) or identity(after) != identity(linked):
            raise LiveObservationError("publication_failed")
        return validate_live_observation(parse_bounded(raw, MAX_BYTES))
    finally:
        os.close(source)


def atomic_write(fd, name, raw, verify):
    # Refuse hostile existing destinations even though replace would not follow them.
    try:
        existing = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    except FileNotFoundError:
        pass
    else:
        try:
            private_file(existing)
        finally:
            os.close(existing)
    temporary = ".pending-" + uuid.uuid4().hex
    out = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
    try:
        with os.fdopen(out, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        verify()
        os.replace(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
    finally:
        try:
            os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError:
            pass


def parent_identity(path):
    with pinned_directory(path) as (fd, verify):
        s = os.fstat(fd)
        if s.st_uid != os.getuid() or s.st_mode & 0o077:
            raise LiveObservationError("publication_failed")
        return f"{s.st_dev}:{s.st_ino}"


def publish_live_observation(parent, identity, event):
    """Serialize bounded writers, atomically replace fixed public metadata."""
    publication = None
    if type(event) is dict and "recent_activity" in event:
        publication = validate_live_observation(event)
        event = publication["recent_activity"][-1]
    validate_event(event)
    try:
        with pinned_directory(parent) as (fd, verify):
            s = os.fstat(fd)
            if (identity != f"{s.st_dev}:{s.st_ino}" or s.st_uid != os.getuid() or s.st_mode & 0o077):
                raise LiveObservationError("publication_failed")
            lock = os.open(".writer.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=fd)
            try:
                private_file(lock)
                deadline = time.monotonic() + 0.45
                while True:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise LiveObservationError("writer_busy")
                        time.sleep(0.005)
                verify()
                linked = os.stat(".writer.lock", dir_fd=fd, follow_symlinks=False)
                if (linked.st_dev, linked.st_ino) != (os.fstat(lock).st_dev, os.fstat(lock).st_ino):
                    raise LiveObservationError("publication_failed")
                key = session_key(event)
                count = 0
                sessions = 0
                exists = False
                # A directory opened before waiting on the lock can retain an
                # older enumeration view (observed on btrfs). Open a fresh scan
                # description only after acquiring the writer lock.
                scan = os.open(".", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    with os.scandir(scan) as entries:
                        for entry in entries:
                            count += 1
                            if count > MAX_SESSIONS + 2:
                                raise LiveObservationError("session_limit")
                            if re.fullmatch(r"[0-9a-f]{64}", entry.name):
                                sessions += 1
                            elif entry.name not in (".writer.lock", "diagnostic.json"):
                                raise LiveObservationError("publication_failed")
                            if entry.name == key:
                                exists = True
                finally:
                    os.close(scan)
                if not exists and sessions >= MAX_SESSIONS:
                    atomic_write(fd, "diagnostic.json", encode({"contract": CONTRACT, "code": "session_limit"}), verify)
                    raise LiveObservationError("session_limit")
                if not exists:
                    os.mkdir(key, 0o700, dir_fd=fd)
                session = os.open(key, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    ss = os.fstat(session)
                    if ss.st_uid != os.getuid() or ss.st_mode & 0o077:
                        raise LiveObservationError("publication_failed")
                    def session_verify():
                        verify()
                        current = os.stat(key, dir_fd=fd, follow_symlinks=False)
                        if (current.st_dev, current.st_ino) != (ss.st_dev, ss.st_ino):
                            raise LiveObservationError("publication_failed")
                    previous = read_snapshot(session)
                    if publication is not None:
                        if previous is None or publication["revision"] > previous["revision"]:
                            raise LiveObservationError("identity_conflict")
                        if publication["revision"] == previous["revision"] and publication != previous:
                            raise LiveObservationError("identity_conflict")
                        return previous
                    result = reduce_live_observation(previous, event)
                    if previous != result:
                        atomic_write(session, "snapshot.json", encode(result), session_verify)
                    return result
                finally:
                    os.close(session)
            finally:
                os.close(lock)
    except LiveObservationError:
        raise
    except (OSError, ValueError):
        raise LiveObservationError("publication_failed") from None


def publish_diagnostic(parent, identity, code):
    """Best-effort bounded producer health, separate from session evidence."""
    if code not in CODES:
        code = "publication_failed"
    with pinned_directory(parent) as (fd, verify):
        s = os.fstat(fd)
        if identity != f"{s.st_dev}:{s.st_ino}" or s.st_uid != os.getuid() or s.st_mode & 0o077:
            raise LiveObservationError("publication_failed")
        lock = os.open(".writer.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=fd)
        try:
            private_file(lock)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            atomic_write(fd, "diagnostic.json", encode({"contract": CONTRACT, "code": code,
                         "observed_at": stamp()}), verify)
        finally:
            os.close(lock)
