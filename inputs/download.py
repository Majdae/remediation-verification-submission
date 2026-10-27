"""Repaired training fix (original kept in evidence/download_original.py). Virtual file map only, no filesystem reads."""

from __future__ import annotations

import json
import pathlib
import posixpath
import sys
import typing
import urllib.parse


def _deny(request_id: str) -> dict[str, typing.Any]:
    return {"request_id": request_id, "status": 403, "body": "Denied"}


def download(request: dict[str, str], files: dict[str, str]) -> dict[str, typing.Any]:
    """Decode once, normalize once, check the exact path that is then looked up."""
    request_id = request["request_id"]
    tenant = request["tenant"]
    #Only red and blue exist. For any other name, the response is 403 (rejected).
    if tenant not in ("red", "blue"):
        return _deny(request_id)
    raw = request["path"]
    # C2: decode exactly once (no recursion); every later step uses this value.
    # unquote does the translation: %2e%2e becomes .., and %20 becomes a space.
    decoded = urllib.parse.unquote(raw)
    # C3: backslashes (literal or encoded) and absolute paths are invalid. Checked
    # after decoding so %5c and %2f-led paths are caught. NUL is rejected as defence in depth.
    #Three things are rejected once the text is translated:

    # a backslash \ (which can act as a disguised separator on Windows)
    # the NULL character (a hidden character, providing additional protection)
    # a path that begins with / (this is an absolute address, starting from the root directory)

    if "\\" in decoded or "\x00" in decoded or decoded.startswith("/"):
        return _deny(request_id)
    # is the true final path.
    lookup = posixpath.normpath(decoded)
    # We check that the correct path starts with exports/red/ (including the trailing /). Otherwise, it's rejected (403).
    if not lookup.startswith("exports/" + tenant + "/"):
        return _deny(request_id)
    content = files.get(lookup)
    if content is None:
        return {"request_id": request_id, "status": 404, "body": "Missing"}
    return {"request_id": request_id, "status": 200, "body": content}


def main() -> None:
    files: dict[str, str] = json.loads(pathlib.Path(__file__).with_name("files.json").read_text(encoding="utf-8"))
    requests: list[dict[str, str]] = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(json.dumps([download(request, files) for request in requests], indent=2))


if __name__ == "__main__":
    main()




#My fix works in four steps. First, I decode the path exactly once. Second, I reject absolute paths and backslashes. Third, I normalize the path, which resolves the dots. Fourth, I check that the final path starts with exports/<tenant>/, with the trailing slash. Only after that do I read the file. So the string I check is the same string I read.”