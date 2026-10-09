"""Validate inert T3 Codex host events for a committed-source review output."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

from .redaction import contains_secret_shape
from ._translation import reviewer_family_from_model


_UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}")
_HEAD_COMMAND = re.compile(r"(?:rtk (?:proxy )?)?git rev-parse(?: --verify)? HEAD(?:\^\{commit\})?")
_STATUS_COMMAND = re.compile(r"(?:rtk (?:proxy )?)?git status --(?:short|porcelain(?:=v1)?)")
_CACHE_OBSERVATION = re.compile(
    r"rtk rg --files /[A-Za-z0-9_./-]+/\.(?:claude|codex)/plugins/cache/depot"
    + re.escape(" | rtk rg 'runtime-resolution\\.md$|workflow-kernel.*SKILL\\.md$' | rtk head -30\n"
                "rtk git remote -v\nrtk git rev-parse HEAD\nrtk git status --short")
)
_COMMIT = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_JSON_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')


def _members(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("invalid native host evidence")
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError("invalid native host evidence")


def _turn(payload):
    metadata = payload.get("internal_chat_message_metadata_passthrough")
    return payload.get("turn_id") or (metadata.get("turn_id") if type(metadata) is dict else None)


def _mapping(value):
    return value if type(value) is dict else {}


def _source_observation(command, stdout, base):
    """Recognize closed read-only programs, never arbitrary shell substrings."""
    if type(command) is not list or not all(type(x) is str for x in command) or type(stdout) is not str:
        return None, None
    if len(command) == 3 and command[0] in {"/bin/bash", "/usr/bin/bash", "bash"} and command[1] in {"-c", "-lc"}:
        script = command[2]
    elif len(command) == 1:
        script = command[0]
    else:
        return None, None
    lines = stdout.splitlines()
    if _HEAD_COMMAND.fullmatch(script):
        if len(lines) != 1 or _COMMIT.fullmatch(lines[0]) is None:
            raise ValueError("ambiguous native source observation")
        return lines[0], None
    if _STATUS_COMMAND.fullmatch(script):
        return None, stdout == ""
    # Two historical observation programs remain recoverable. Their other
    # commands cannot print a bare commit: status has a prefix, remote has a
    # name/URL, asset lookup prints absolute paths, and diff-stat has columns.
    git_batch = "git status --short --branch && git rev-parse HEAD && git diff --stat " + base + "..HEAD"
    if script != git_batch and _CACHE_OBSERVATION.fullmatch(script) is None:
        return None, None
    hashes = [(i, line) for i, line in enumerate(lines) if _COMMIT.fullmatch(line)]
    if len(hashes) != 1:
        raise ValueError("ambiguous native source observation")
    position, head = hashes[0]
    clean = (position == 1 and lines[0].startswith("## ")) if script == git_batch else position == len(lines) - 1
    if not clean:
        raise ValueError("native source was not clean")
    return head, True


def _source_cwd(value):
    """Compare recorded locations without accessing historical filesystems."""
    if type(value) is not str:
        raise ValueError("missing native source location")
    parsed = urlsplit(value)
    path = unquote(parsed.path)
    if (parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}
            or parsed.query or parsed.fragment or not PurePosixPath(path).is_absolute()
            or ".." in PurePosixPath(path).parts or any(ord(c) < 32 or ord(c) == 127 for c in path)):
        raise ValueError("invalid native source location")
    return str(PurePosixPath(path))


def validate_native_output(trace_bytes, output_bytes, value, index_bytes):
    """Require actual source, file-write and completion witnesses, never execute them.

    Excerpts may omit unrelated events, but retain original ordered host records.
    A dirty/staged historical tree is not inferred from a commit observation.
    """
    if len(trace_bytes) > 2 * 1024 * 1024 or value["source"]["worktree_ref"] is not None:
        raise ValueError("native evidence requires committed source")
    records = []
    for line in trace_bytes.splitlines():
        if len(line) > 512 * 1024 or len(records) >= 4096 or not line:
            raise ValueError("invalid native host evidence")
        record = json.loads(line, object_pairs_hook=_members, parse_constant=_invalid_constant)
        if type(record) is not dict or type(record.get("payload")) is not dict:
            raise ValueError("invalid native host evidence")
        ordinal = record.get("ordinal")
        if type(ordinal) is not int or ordinal < 0 or records and ordinal <= records[-1]["ordinal"]:
            raise ValueError("invalid native host evidence")
        records.append(record)
    sessions = [r["payload"] for r in records if r.get("type") == "session_meta"]
    if len(sessions) != 1 or records[0].get("type") != "session_meta" or records[0]["ordinal"] != 0:
        raise ValueError("invalid native host evidence")
    meta = sessions[0]
    thread, parent, agent = meta.get("id"), meta.get("parent_thread_id"), meta.get("agent_path")
    if len(index_bytes) > 64 * 1024:
        raise ValueError("invalid native extraction index")
    index = json.loads(index_bytes, object_pairs_hook=_members, parse_constant=_invalid_constant)
    fields = {"schema_version", "full_trace_digest", "excerpt_digest", "thread_id", "original_line_numbers", "original_ordinals"}
    if (type(index) is not dict or set(index) != fields
            or type(index["schema_version"]) is not int or index["schema_version"] != 1
            or type(index["full_trace_digest"]) is not str or _DIGEST.fullmatch(index["full_trace_digest"]) is None
            or index["excerpt_digest"] != "sha256:" + hashlib.sha256(trace_bytes).hexdigest()
            or index["thread_id"] != thread
            or index["original_ordinals"] != [r["ordinal"] for r in records]
            or index["original_line_numbers"] != [r["ordinal"] + 1 for r in records]
            or any(type(n) is not int for field in ("original_ordinals", "original_line_numbers") for n in index[field])):
        raise ValueError("invalid native extraction index")
    spawn = _mapping(_mapping(_mapping(meta.get("source")).get("subagent")).get("thread_spawn"))
    if (meta.get("originator") != "T3 Code" or meta.get("thread_source") != "subagent"
            or not all(type(x) is str and _UUID.fullmatch(x) for x in (thread, parent))
            or thread == parent or spawn.get("parent_thread_id") != parent
            or spawn.get("agent_path") != agent or type(spawn.get("depth")) is not int
            or spawn["depth"] < 1 or type(agent) is not str
            or re.fullmatch(r"/root(?:/[a-z0-9_]+)+", agent) is None):
        raise ValueError("invalid native host evidence")
    reviewer = "native-" + hashlib.sha256(thread.encode()).hexdigest()[:16]
    if value["reviewer"] != reviewer:
        raise ValueError("native participant mismatch")
    text = output_bytes.decode("utf-8")
    matches = []
    for index, record in enumerate(records):
        payload = record["payload"]
        item = _mapping(payload.get("item"))
        if (record.get("type") != "event_msg" or payload.get("type") != "item_completed"
                or item.get("type") != "FileChange" or item.get("status") != "completed"
                or payload.get("thread_id") != thread):
            continue
        for path, change in _mapping(item.get("changes")).items():
            if (type(path) is str and PurePosixPath(path).is_absolute()
                    and ".." not in PurePosixPath(path).parts
                    and path.endswith("/" + value["literal"]["output_ref"])
                    and type(change) is dict and change == {"type": "add", "content": text}):
                matches.append((index, payload.get("turn_id"), path))
    if len(matches) != 1:
        raise ValueError("native output witness mismatch")
    index, turn, path = matches[0]
    if type(turn) is not str or _UUID.fullmatch(turn) is None:
        raise ValueError("invalid native host evidence")
    before, after = records[:index], records[index + 1:]
    contexts = [r["payload"] for r in before if r.get("type") == "turn_context" and _turn(r["payload"]) == turn]
    assignments = [r for r in before if r.get("type") == "response_item"
                   and r["payload"].get("type") == "agent_message"
                   and _turn(r["payload"]) == turn and r["payload"].get("recipient") == agent
                   and r["payload"].get("author") == agent.rsplit("/", 1)[0]]
    if len(contexts) != 1 or not assignments:
        raise ValueError("missing native assignment evidence")
    assignment_ordinal = min(r["ordinal"] for r in assignments)
    heads, statuses = [], []
    for record in before:
        payload, item = record["payload"], _mapping(record["payload"].get("item"))
        if (record.get("type") == "event_msg" and payload.get("type") == "item_completed"
                and record["ordinal"] > assignment_ordinal
                and payload.get("thread_id") == thread and _turn(payload) == turn
                and item.get("type") == "CommandExecution" and item.get("status") == "completed"
                and type(item.get("exit_code")) is int and item["exit_code"] == 0
                ):
            head, clean = _source_observation(item.get("command"), item.get("stdout"), value["source"]["base"])
            if head is None and clean is None:
                continue
            cwd = _source_cwd(item.get("cwd"))
            if head is not None:
                heads.append((record["ordinal"], head, cwd, clean))
            if clean is not None:
                statuses.append((record["ordinal"], cwd, clean))
    patch = "*** Add File: " + path + "\n" + "".join("+" + line + "\n" for line in text.splitlines())
    calls = []
    for record in before:
        payload = record["payload"]
        if (record.get("type") == "response_item" and payload.get("type") == "custom_tool_call"
                and payload.get("name") == "exec" and payload.get("status") == "completed"
                and _turn(payload) == turn and type(payload.get("input")) is str):
            strings = []
            for match in _JSON_STRING.finditer(payload["input"]):
                try:
                    strings.append(json.loads(match.group()))
                except ValueError:
                    continue
            if any(patch in literal for literal in strings):
                call_id = payload.get("call_id")
                if type(call_id) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,256}", call_id) is None:
                    raise ValueError("invalid native call identity")
                calls.append(call_id)
    results = [r for r in after if r.get("type") == "response_item"
               and r["payload"].get("type") == "custom_tool_call_output"
               and r["payload"].get("call_id") in calls]
    finals = [r for r in after if r.get("type") == "response_item"
              and r["payload"].get("type") == "message" and r["payload"].get("role") == "assistant"
              and r["payload"].get("phase") == "final_answer" and _turn(r["payload"]) == turn]
    completions = [r for r in after if r.get("type") == "event_msg"
                   and r["payload"].get("type") == "task_complete" and _turn(r["payload"]) == turn]
    if ({h[1] for h in heads} != {value["source"]["head"]} or len({h[2] for h in heads}) != 1
            or len(calls) != 1 or len(results) != 1 or len(finals) != 1 or len(completions) != 1):
        raise ValueError("incomplete native host evidence")
    last_head = heads[-1]
    same_source = [s for s in statuses if s[1] == last_head[2] and s[0] >= last_head[0]]
    # Equality is allowed only for the closed combined observation, whose
    # command/result proves both facts. Standalone status must follow HEAD.
    if not same_source or same_source[-1][2] is not True:
        raise ValueError("incomplete native clean-source evidence")
    for record in (*results, *finals, *completions):
        payload = record["payload"]
        if (payload.get("thread_id", thread) != thread
                or _turn(payload) is not None and _turn(payload) != turn):
            raise ValueError("native completion identity mismatch")
    if not results[0]["ordinal"] < finals[0]["ordinal"] < completions[0]["ordinal"]:
        raise ValueError("invalid native completion order")
    tool_output = results[0]["payload"].get("output")
    if (type(tool_output) is not list or not tool_output
            or type(tool_output[0]) is not dict
            or not str(tool_output[0].get("text", "")).startswith("Script completed\n")):
        raise ValueError("incomplete native tool execution")
    recorded_timestamp = completions[0].get("timestamp")
    if type(recorded_timestamp) is not str:
        raise ValueError("invalid native completion time")
    timestamp = datetime.fromisoformat(recorded_timestamp.replace("Z", "+00:00"))
    declared = value["provenance"]["executed_at"]
    if timestamp.tzinfo is None or declared is not None and datetime.fromisoformat(declared.replace("Z", "+00:00")) != timestamp:
        raise ValueError("native timestamp mismatch")
    for identity in (meta.get("model_provider"), contexts[0].get("model")):
        if identity is not None and (type(identity) is not str or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", identity) is None or contains_secret_shape(identity)):
            raise ValueError("invalid native model evidence")
    model = contexts[0].get("model") or "not_reported"
    try:
        family = reviewer_family_from_model(model) if model != "not_reported" else "unknown"
    except ValueError:
        # Preserve the observation in the trace; an unclassified identity is
        # unavailable summary metadata, never an inspection eligibility gate.
        model, family = "not_reported", "unknown"
    return {"reviewer": reviewer, "lane": value["lane"], "requested_provider": "unknown",
            "attempted_provider": meta.get("model_provider") or "unknown",
            "implemented_by": "codex-collaboration", "provider": meta.get("model_provider") or "unknown",
            "model": model, "implementer_family": "unknown",
            "reviewer_family": family, "resolution_reason": "native-host-witness-validated",
            "evidence_refs": [value["literal"]["output_ref"]], "raw_output_ref": "review/pending-output.json",
            "raw_output_digest": "sha256:" + "0" * 64, "finding_count": len(value["result"]["findings"])}
