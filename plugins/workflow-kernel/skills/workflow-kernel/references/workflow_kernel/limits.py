"""Shared resource limits and bounded JSON document loading."""

from __future__ import annotations

import json
from pathlib import Path

from .redaction import MAX_PAYLOAD_DEPTH


MAX_JSON_DOCUMENT_DEPTH = MAX_PAYLOAD_DEPTH
MAX_JSON_INTEGER_DIGITS = 4_096
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_JSON_WHITESPACE = frozenset(" \t\r\n")
_SCALAR_TOKENS = frozenset({"string", "scalar"})


class JSONDocumentSyntaxError(ValueError):
    """The document is not valid JSON syntax."""


class JSONDocumentDepthError(ValueError):
    """A syntactically valid document exceeds the structural depth limit."""


def bounded_json_int(raw: str) -> int:
    """Accumulate a signed JSON integer without interpreter digit limits."""
    if type(raw) is not str:
        raise ValueError("JSON integer must be text")
    negative = raw.startswith("-")
    digits = raw[1:] if negative else raw
    if (
        not digits
        or len(digits) > MAX_JSON_INTEGER_DIGITS
        or any(character < "0" or character > "9" for character in digits)
    ):
        raise ValueError("invalid or oversized JSON integer")
    value = 0
    for character in digits:
        value = value * 10 + ord(character) - ord("0")
    return -value if negative else value


def _json_tokens(document: str):
    """Yield JSON grammar tokens without materializing nested containers."""
    index = 0
    length = len(document)
    while index < length:
        character = document[index]
        if character in _JSON_WHITESPACE:
            index += 1
            continue
        if character in "{}[],:":
            yield character
            index += 1
            continue
        if character == '"':
            index += 1
            while index < length:
                character = document[index]
                if character == '"':
                    index += 1
                    yield "string"
                    break
                if ord(character) < 0x20:
                    raise JSONDocumentSyntaxError
                if character == "\\":
                    index += 1
                    if index >= length:
                        raise JSONDocumentSyntaxError
                    escaped = document[index]
                    if escaped == "u":
                        if (
                            index + 4 >= length
                            or any(
                                value not in _HEX_DIGITS
                                for value in document[index + 1:index + 5]
                            )
                        ):
                            raise JSONDocumentSyntaxError
                        index += 5
                        continue
                    if escaped not in '"\\/bfnrt':
                        raise JSONDocumentSyntaxError
                index += 1
            else:
                raise JSONDocumentSyntaxError
            continue
        matched_constant = False
        for constant in ("-Infinity", "Infinity", "NaN", "true", "false", "null"):
            if document.startswith(constant, index):
                index += len(constant)
                yield "scalar"
                matched_constant = True
                break
        if matched_constant:
            continue
        if character == "-" or "0" <= character <= "9":
            if character == "-":
                index += 1
                if index >= length or not "0" <= document[index] <= "9":
                    raise JSONDocumentSyntaxError
            if document[index] == "0":
                index += 1
            else:
                while index < length and "0" <= document[index] <= "9":
                    index += 1
            if index < length and document[index] == ".":
                index += 1
                if index >= length or not "0" <= document[index] <= "9":
                    raise JSONDocumentSyntaxError
                while index < length and "0" <= document[index] <= "9":
                    index += 1
            if index < length and document[index] in "eE":
                index += 1
                if index < length and document[index] in "+-":
                    index += 1
                if index >= length or not "0" <= document[index] <= "9":
                    raise JSONDocumentSyntaxError
                while index < length and "0" <= document[index] <= "9":
                    index += 1
            yield "scalar"
            continue
        raise JSONDocumentSyntaxError


def _scan_json_document(document: str) -> bool:
    """Validate JSON grammar iteratively and return whether depth is excessive."""
    frames = []
    root_state = "value"
    over_depth = False

    def start_value(token: str) -> None:
        nonlocal over_depth
        if token in _SCALAR_TOKENS:
            return
        if token == "[":
            frames.append(["array", "first_value_or_end"])
        elif token == "{":
            frames.append(["object", "first_key_or_end"])
        else:
            raise JSONDocumentSyntaxError
        if len(frames) > MAX_JSON_DOCUMENT_DEPTH:
            over_depth = True

    for token in _json_tokens(document):
        if not frames:
            if root_state != "value":
                raise JSONDocumentSyntaxError
            root_state = "done"
            start_value(token)
            continue

        kind, state = frames[-1]
        if kind == "array":
            if state == "first_value_or_end" and token == "]":
                frames.pop()
            elif state in {"first_value_or_end", "value"}:
                frames[-1][1] = "comma_or_end"
                start_value(token)
            elif state == "comma_or_end" and token == ",":
                frames[-1][1] = "value"
            elif state == "comma_or_end" and token == "]":
                frames.pop()
            else:
                raise JSONDocumentSyntaxError
            continue

        if state == "first_key_or_end" and token == "}":
            frames.pop()
        elif state in {"first_key_or_end", "key"} and token == "string":
            frames[-1][1] = "colon"
        elif state == "colon" and token == ":":
            frames[-1][1] = "value"
        elif state == "value":
            frames[-1][1] = "comma_or_end"
            start_value(token)
        elif state == "comma_or_end" and token == ",":
            frames[-1][1] = "key"
        elif state == "comma_or_end" and token == "}":
            frames.pop()
        else:
            raise JSONDocumentSyntaxError

    if frames or root_state != "done":
        raise JSONDocumentSyntaxError
    return over_depth


def load_json_document(path: Path) -> object:
    """Load one syntactically valid JSON document within owned limits."""
    document = path.read_text(encoding="utf-8")
    if _scan_json_document(document):
        raise JSONDocumentDepthError
    return json.loads(document, parse_int=bounded_json_int)
