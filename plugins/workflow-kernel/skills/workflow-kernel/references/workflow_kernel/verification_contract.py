"""Shared closed vocabulary and digest primitives for repository verification."""

from __future__ import annotations

import hashlib
import json
import re


BOUNDARY_CHOICES = (
    "chunk", "revision_batch", "execution_level", "merge_candidate",
    "post_merge",
)
BOUNDARIES = frozenset(BOUNDARY_CHOICES)
TIERS = frozenset({
    "doctor", "fast", "focused", "full", "race", "harness", "remote",
})
OWNERS = frozenset({"local", "github", "blueprint", "other", "unresolved"})
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical_bytes(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def digest(value):
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def byte_digest(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()
