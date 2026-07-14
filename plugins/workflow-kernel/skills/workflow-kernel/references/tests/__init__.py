"""Workflow kernel tests."""
import hashlib


def detail_digest(value):
    return "value-sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def detail_key_digest(value):
    return "key-sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()
