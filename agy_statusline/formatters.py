"""Segment formatters and two-line status builders."""

import time
import subprocess
from pathlib import Path
from datetime import UTC, datetime

from agy_statusline.theme import pct_color
from agy_statusline.models import Theme, StatusData, RateLimitWindow
from agy_statusline.constants import (
    RESET,
    ICON_CTX,
    ICON_DIR,
    ICON_GIT,
    ICON_VIM,
    BAR_EMPTY,
    ICON_WARN,
    BAR_FILLED,
    ICON_MODEL,
    BAR_SEGMENTS,
)


def format_tokens(count: int) -> str:
    """Format a token count into a compact human-readable string.

    Args:
        count (int): Token count.

    Returns:
        str: Formatted string (e.g., ``"512"``, ``"1.2k"``, ``"123k"``, ``"1.5M"``).
    """
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 100_000:
        return f"{round(count / 1_000)}k"
    if count >= 1_000:
        return f"{count / 1_000:.1f}k"
    return str(count)


def format_countdown(seconds: int) -> str:
    """Format remaining seconds into a compact duration string.

    Args:
        seconds (int): Seconds remaining until reset.

    Returns:
        str: Compact duration string (e.g., ``"0m"``, ``"42m"``, ``"2h15m"``, ``"3d4h"``).
    """
    if seconds <= 0:
        return "0m"
    minutes, _ = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days > 0:
        return f"{days}d{hours}h"
    if hours > 0:
        return f"{hours}h{minutes:02d}m" if minutes > 0 else f"{hours}h"
    return f"{minutes}m"


def resets_at_to_epoch(resets_at: str) -> float | None:
    """Convert an ISO-8601 timestamp string to a Unix epoch timestamp.

    Args:
        resets_at (str): ISO-8601 datetime string (e.g., ``"2026-11-14T15:00:00Z"``).

    Returns:
        float | None: Unix timestamp in seconds, or ``None`` if parsing fails.
    """
    if not resets_at:
        return None
    normalized = resets_at.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp()


def usage_segment_str(
    label: str,
    window: RateLimitWindow,
    theme: Theme,
    now: float | None = None,
) -> str:
    """Format a quota window segment with usage percentage and reset countdown.

    Args:
        label (str): Short window label (e.g., ``"5h"`` or ``"7d"``).
        window (RateLimitWindow): Parsed rate-limit window data.
        theme (Theme): Active color theme.
        now (float | None): Optional current epoch time for deterministic testing.

    Returns:
        str: ANSI-colored quota segment string.
    """
    used_pct = window.used_percentage if window.used_percentage is not None else 0.0
    color = pct_color(used_pct, theme)
    pct_text = f"{round(used_pct)}%"

    countdown = ""
    if window.reset_in_seconds is not None:
        countdown = format_countdown(window.reset_in_seconds)
    elif window.resets_at:
        epoch = resets_at_to_epoch(window.resets_at)
        if epoch is not None:
            current_time = time.time() if now is None else now
            remaining = max(0, int(epoch - current_time))
            countdown = format_countdown(remaining)

    if countdown:
        return f"{theme.dim}{label}{RESET} {color}{pct_text}{RESET} {theme.dim}({countdown}){RESET}"
    return f"{theme.dim}{label}{RESET} {color}{pct_text}{RESET}"


def context_bar_str(used_pct: float, theme: Theme, segments: int = BAR_SEGMENTS) -> str:
    """Build a 16-segment ANSI-colored context usage progress bar.

    Appends a red warning badge when usage reaches or exceeds 90%.

    Args:
        used_pct (float): Context window usage percentage (0-100).
        theme (Theme): Active color theme.
        segments (int): Total number of bar segments (defaults to ``BAR_SEGMENTS``).

    Returns:
        str: Formatted progress bar string with percentage and optional warning icon.
    """
    clamped = max(0.0, min(100.0, used_pct))
    filled = round((clamped / 100.0) * segments)
    filled = max(0, min(segments, filled))
    empty = segments - filled

    color = pct_color(clamped, theme)
    bar = f"{color}{BAR_FILLED * filled}{theme.dim}{BAR_EMPTY * empty}{RESET}"
    pct_str = f"{color}{round(clamped)}%{RESET}"
    warn = f" {theme.red}{ICON_WARN}{RESET}" if clamped >= 90.0 else ""
    return f"{bar} {pct_str}{warn}"


def tokens_str(data: StatusData, theme: Theme) -> str:
    """Format input/output and optional cache token counts.

    Uses ``data.current_usage`` when available; otherwise falls back to
    ``data.total_input_tokens`` and ``data.total_output_tokens``. Cache write
    (``cw``) and cache read (``cr``) sub-fields are shown only when non-zero.

    Args:
        data (StatusData): Parsed status data.
        theme (Theme): Active color theme.

    Returns:
        str: ANSI-formatted token summary string.
    """
    if data.current_usage is not None:
        in_tok = data.current_usage.input_tokens
        out_tok = data.current_usage.output_tokens
        cw_tok = data.current_usage.cache_creation_input_tokens
        cr_tok = data.current_usage.cache_read_input_tokens
    else:
        in_tok = data.total_input_tokens
        out_tok = data.total_output_tokens
        cw_tok = 0
        cr_tok = 0

    parts = [
        f"{theme.dim}in:{RESET}{theme.fg}{format_tokens(in_tok)}{RESET}",
        f"{theme.dim}out:{RESET}{theme.fg}{format_tokens(out_tok)}{RESET}",
    ]
    if cw_tok > 0:
        parts.append(f"{theme.dim}cw:{RESET}{theme.fg}{format_tokens(cw_tok)}{RESET}")
    if cr_tok > 0:
        parts.append(f"{theme.dim}cr:{RESET}{theme.fg}{format_tokens(cr_tok)}{RESET}")
    return " ".join(parts)


def shorten_dir(cwd: str, home: str | None = None) -> str:
    """Shorten a directory path by replacing the home prefix with ``~``.

    Paths deeper than 3 components are collapsed to ``~/.../parent/leaf``.

    Args:
        cwd (str): Current working directory path.
        home (str | None): Optional home directory override for testing.

    Returns:
        str: Shortened display path.
    """
    if not cwd or cwd == ".":
        return "."
    home_path = Path(home) if home is not None else Path.home()
    cwd_path = Path(cwd)
    try:
        rel = cwd_path.relative_to(home_path)
        parts = rel.parts
        if not parts:
            return "~"
        if len(parts) > 3:
            return f"~/.../{parts[-2]}/{parts[-1]}"
        return f"~/{'/'.join(parts)}"
    except ValueError:
        parts = cwd_path.parts
        if len(parts) > 4:
            return f"/.../{parts[-2]}/{parts[-1]}"
        return str(cwd_path)


def git_info_str(
    cwd: str,
    theme: Theme,
    fallback_branch: str = "",
    fallback_dirty: bool = False,
) -> str:
    """Inspect git status for cwd and format branch plus staged/unstaged/untracked counts.

    Falls back to ``fallback_branch`` / ``fallback_dirty`` from stdin ``vcs``
    when the ``git`` subprocess is unavailable or returns an error.

    Args:
        cwd (str): Working directory to inspect.
        theme (Theme): Active color theme.
        fallback_branch (str): Branch name from stdin ``vcs`` payload.
        fallback_dirty (bool): Dirty flag from stdin ``vcs`` payload.

    Returns:
        str: Formatted git status segment, or ``""`` if not in a repository.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, "status", "--porcelain", "-b"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
    except OSError, subprocess.SubprocessError:
        proc = None

    if proc is None or proc.returncode != 0:
        if not fallback_branch:
            return ""
        color = theme.git_dirty if fallback_dirty else theme.git
        dirty_mark = "*" if fallback_dirty else ""
        return f"{color}{ICON_GIT} {fallback_branch}{dirty_mark}{RESET}"

    lines = proc.stdout.splitlines()
    if not lines:
        return ""

    branch = fallback_branch or "HEAD"
    header = lines[0]
    if header.startswith("## "):
        branch_part = header[3:].split("...")[0].strip()
        if branch_part.startswith("No commits yet on "):
            branch_part = branch_part.removeprefix("No commits yet on ").strip()
        elif branch_part.startswith("HEAD (no branch)"):
            branch_part = "HEAD"
        if branch_part:
            branch = branch_part

    staged = 0
    unstaged = 0
    untracked = 0
    for line in lines[1:]:
        if len(line) < 2:
            continue
        x, y = line[0], line[1]
        if x == "?" and y == "?":
            untracked += 1
        else:
            if x not in {" ", "?"}:
                staged += 1
            if y not in {" ", "?"}:
                unstaged += 1

    counts: list[str] = []
    if staged > 0:
        counts.append(f"+{staged}")
    if unstaged > 0:
        counts.append(f"~{unstaged}")
    if untracked > 0:
        counts.append(f"?{untracked}")

    is_dirty = bool(counts)
    color = theme.git_dirty if is_dirty else theme.git
    suffix = f" {' '.join(counts)}" if counts else ""
    return f"{color}{ICON_GIT} {branch}{suffix}{RESET}"


def build_line1(data: StatusData, theme: Theme) -> str:
    """Build Line 1: Model (+ Effort) | Context Bar (16 segs) | Tokens.

    Args:
        data (StatusData): Parsed status data.
        theme (Theme): Active color theme.

    Returns:
        str: ANSI-formatted first line of the status output.
    """
    sep = f" {theme.sep}│{RESET} "
    effort_suffix = f" ({data.effort})" if data.effort else ""
    model_seg = f"{theme.model}{ICON_MODEL} {data.model_name}{effort_suffix}{RESET}"
    ctx_seg = f"{theme.dim}{ICON_CTX}{RESET} {context_bar_str(data.used_percentage, theme)}"
    tok_seg = tokens_str(data, theme)
    return sep.join([model_seg, ctx_seg, tok_seg])


def build_line2(data: StatusData, theme: Theme, now: float | None = None) -> str:
    """Build Line 2: Directory | Git Branch & Status | 5h usage | 7d usage | Vim / Mode.

    Args:
        data (StatusData): Parsed status data.
        theme (Theme): Active color theme.
        now (float | None): Optional current epoch time for deterministic testing.

    Returns:
        str: ANSI-formatted second line of the status output.
    """
    sep = f" {theme.sep}│{RESET} "
    segments: list[str] = [f"{theme.dir}{ICON_DIR} {shorten_dir(data.cwd)}{RESET}"]

    git_seg = git_info_str(data.cwd, theme, data.vcs_branch, data.vcs_dirty)
    if git_seg:
        segments.append(git_seg)

    if data.five_hour is not None:
        segments.append(usage_segment_str("5h", data.five_hour, theme, now=now))
    if data.seven_day is not None:
        segments.append(usage_segment_str("7d", data.seven_day, theme, now=now))

    if data.vim_mode:
        segments.append(f"{theme.vim}{ICON_VIM} {data.vim_mode}{RESET}")

    return sep.join(segments)
