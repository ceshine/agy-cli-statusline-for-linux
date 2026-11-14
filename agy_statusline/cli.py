"""CLI entry point for agy-statusline."""

import sys
import json
from typing import Any

from agy_statusline.theme import build_theme
from agy_statusline.parser import parse_status_data
from agy_statusline.formatters import build_line1, build_line2


def render_statusline(raw_input: str, now: float | None = None) -> str:
    """Render the two-line ANSI status output from raw stdin JSON text.

    Args:
        raw_input (str): Raw JSON string read from stdin.
        now (float | None): Optional current epoch time for deterministic testing.

    Returns:
        str: Two-line ANSI-formatted status string.
    """
    payload: dict[str, Any]
    try:
        parsed = json.loads(raw_input) if raw_input.strip() else {}
        payload = parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        payload = {}

    data = parse_status_data(payload)
    theme = build_theme()
    line1 = build_line1(data, theme)
    line2 = build_line2(data, theme, now=now)
    return f"{line1}\n{line2}"


def main() -> None:
    """Read Antigravity CLI status JSON from stdin and print the 2-line status."""
    raw_input = sys.stdin.read()
    print(render_statusline(raw_input))
