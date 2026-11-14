"""Terminal theme detection and color helpers."""

import os
from collections.abc import Mapping

from agy_statusline.models import Theme

DARK_THEME = Theme(
    name="dark",
    fg="\033[38;5;252m",
    dim="\033[38;5;242m",
    model="\033[1;38;5;111m",
    dir="\033[38;5;75m",
    git="\033[38;5;114m",
    git_dirty="\033[38;5;215m",
    green="\033[38;5;114m",
    yellow="\033[38;5;221m",
    red="\033[1;38;5;203m",
    vim="\033[1;38;5;183m",
    sep="\033[38;5;239m",
)

LIGHT_THEME = Theme(
    name="light",
    fg="\033[38;5;236m",
    dim="\033[38;5;245m",
    model="\033[1;38;5;26m",
    dir="\033[38;5;25m",
    git="\033[38;5;28m",
    git_dirty="\033[38;5;166m",
    green="\033[38;5;28m",
    yellow="\033[38;5;136m",
    red="\033[1;38;5;160m",
    vim="\033[1;38;5;91m",
    sep="\033[38;5;250m",
)


def detect_theme(env: Mapping[str, str] | None = None) -> str:
    """Detect whether the terminal uses a dark or light color scheme.

    Checks ``STATUSLINE_THEME`` first, then ``COLORFGBG`` (e.g. ``15;0``).
    Defaults to ``"dark"``.

    Args:
        env (Mapping[str, str] | None): Environment mapping to inspect; defaults to ``os.environ``.

    Returns:
        str: Either ``"dark"`` or ``"light"``.
    """
    environ = os.environ if env is None else env
    explicit = environ.get("STATUSLINE_THEME", "").strip().lower()
    if explicit in {"light", "dark"}:
        return explicit

    colorfgbg = environ.get("COLORFGBG", "").strip()
    if colorfgbg:
        parts = colorfgbg.split(";")
        try:
            bg = int(parts[-1])
        except ValueError:
            return "dark"
        if bg >= 7 and bg != 8:
            return "light"
    return "dark"


def build_theme(theme_name: str | None = None, env: Mapping[str, str] | None = None) -> Theme:
    """Build a Theme instance for the given or auto-detected theme name.

    Args:
        theme_name (str | None): Explicit theme name (``"dark"`` or ``"light"``), or ``None`` to auto-detect.
        env (Mapping[str, str] | None): Optional environment mapping passed to ``detect_theme``.

    Returns:
        Theme: The selected color theme.
    """
    resolved = theme_name.strip().lower() if theme_name else detect_theme(env)
    return LIGHT_THEME if resolved == "light" else DARK_THEME


def pct_color(pct: float, theme: Theme) -> str:
    """Return the ANSI color code corresponding to a usage percentage.

    Args:
        pct (float): Percentage value in ``[0, 100]``.
        theme (Theme): Active color theme.

    Returns:
        str: ANSI escape sequence for green (<70), yellow (70-89.9), or red (>=90).
    """
    if pct >= 90.0:
        return theme.red
    if pct >= 70.0:
        return theme.yellow
    return theme.green
