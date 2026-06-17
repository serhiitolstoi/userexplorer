"""Render per-user blobs + meta into the HTML template.

Replaces two sentinels in template.html with actual JSON, then writes
atomically (temp + rename) to avoid partial output on crash.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import webbrowser
from pathlib import Path
from typing import Any

_TEMPLATE = Path(__file__).parent / "template.html"
_LOGIC = Path(__file__).parent / "logic.js"
_DATA_SENTINEL = "/*__USERLENS_DATA__*/"
_META_SENTINEL = "/*__USERLENS_META__*/"
_LOGIC_SENTINEL = "/*__USERLENS_LOGIC__*/"


def render(
    blobs: list[dict[str, Any]],
    meta: dict[str, Any],
    out_path: Path,
    *,
    open_browser: bool = True,
) -> None:
    """Write self-contained HTML to out_path; optionally open in browser."""
    template = _TEMPLATE.read_text(encoding="utf-8")
    logic_js = _LOGIC.read_text(encoding="utf-8")

    data_json = json.dumps(blobs, separators=(",", ":"), default=str)
    meta_json = json.dumps(meta, separators=(",", ":"), default=str)

    # Inline the shared analytics module first (it contains no sentinels), then
    # the data/meta payloads. Keeps the output a single self-contained file.
    html = (
        template.replace(_LOGIC_SENTINEL, logic_js)
        .replace(_DATA_SENTINEL, data_json)
        .replace(_META_SENTINEL, meta_json)
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=out_path.parent, prefix=".userexplorer_", suffix=".html")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(html)
        os.replace(tmp, out_path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise

    if open_browser:
        webbrowser.open(out_path.resolve().as_uri())
