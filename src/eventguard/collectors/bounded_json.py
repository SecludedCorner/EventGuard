"""Small fail-closed boundary for already byte-bounded collector JSON.

This is not a second JSON parser: the string-aware scan only caps nesting before
the standard decoder allocates nested containers. The decoder still validates
syntax and unescapes keys before duplicate detection.
"""
from __future__ import annotations

import json

MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_JSON_DEPTH = 32


class BoundedJSONError(ValueError):
    """A fixed reason code, never source text or an untrusted key."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BoundedJSONError("query_json_duplicate_key")
        result[key] = value
    return result


def loads(value):
    """Decode at most 4 MiB and 32 container levels, rejecting repeated keys."""
    if not isinstance(value, str):
        raise BoundedJSONError("invalid_query_output")
    if len(value) > MAX_JSON_BYTES or len(value.encode("utf-8")) > MAX_JSON_BYTES:
        raise BoundedJSONError("query_output_limit_exceeded")
    depth, in_string, escaped = 0, False, False
    for character in value:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise BoundedJSONError("query_json_depth_exceeded")
        elif character in "]}":
            depth = max(0, depth - 1)
    return json.loads(value, object_pairs_hook=_unique_object)
