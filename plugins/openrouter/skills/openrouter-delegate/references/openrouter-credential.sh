#!/usr/bin/env bash
# Shared strict resolver for OPENROUTER_API_KEY / OPENROUTER_API_KEY_FILE.

load_openrouter_api_key() {
  if [ -n "${OPENROUTER_API_KEY:-}" ] && [ -n "${OPENROUTER_API_KEY_FILE:-}" ]; then
    return 2
  fi
  if [ -n "${OPENROUTER_API_KEY:-}" ]; then
    export OPENROUTER_API_KEY
    return 0
  fi
  [ -n "${OPENROUTER_API_KEY_FILE:-}" ] && [ -x /usr/bin/python3 ] || return 1
  OPENROUTER_API_KEY="$(/usr/bin/python3 -I - "$OPENROUTER_API_KEY_FILE" <<'PY'
import os
import stat
import sys

path = sys.argv[1]
try:
    metadata = os.lstat(path)
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise ValueError
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise ValueError
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise ValueError
        value = os.read(descriptor, 8193)
    finally:
        os.close(descriptor)
    if value.endswith(b"\r\n"):
        value = value[:-2]
    elif value.endswith(b"\n"):
        value = value[:-1]
    if not value or len(value) > 8192 or b"\n" in value or b"\r" in value or b"\0" in value:
        raise ValueError
    sys.stdout.write(value.decode("utf-8"))
except (OSError, UnicodeDecodeError, ValueError):
    raise SystemExit(1)
PY
)" || return 1
  export OPENROUTER_API_KEY
}
