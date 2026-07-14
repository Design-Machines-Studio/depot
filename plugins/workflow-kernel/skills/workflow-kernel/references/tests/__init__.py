"""Workflow kernel tests."""
import hashlib
import os


def swap_parent_after_relative_stat(parent, entry_name):
    """Return one stat injector shared by present and missing absence checks."""
    parent = parent.resolve()
    moved = parent.parent / "moved"
    original_stat = os.stat
    swapped = False

    def injected(path, *args, **kwargs):
        nonlocal swapped
        matches = (path == entry_name and kwargs.get("dir_fd") is not None
                   and not swapped)
        try:
            result = original_stat(path, *args, **kwargs)
        except FileNotFoundError:
            if matches:
                swapped = True
                parent.rename(moved)
                parent.mkdir()
            raise
        if matches:
            swapped = True
            parent.rename(moved)
            parent.mkdir()
            (parent / entry_name).touch()
        return result

    return injected


def detail_digest(value):
    return "value-sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def detail_key_digest(value):
    return "key-sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()
