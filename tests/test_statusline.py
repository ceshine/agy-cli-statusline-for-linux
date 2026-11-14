"""Unit tests for agy_statusline."""

import re
import json
import subprocess
from unittest.mock import patch, MagicMock

from agy_statusline.cli import render_statusline
from agy_statusline.theme import pct_color, DARK_THEME, LIGHT_THEME, build_theme, detect_theme
from agy_statusline.models import StatusData, RateLimitWindow
from agy_statusline.parser import parse_status_data
from agy_statusline.constants import ICON_WARN
from agy_statusline.formatters import (
    tokens_str,
    build_line1,
    build_line2,
    shorten_dir,
    git_info_str,
    format_tokens,
    context_bar_str,
    format_countdown,
    usage_segment_str,
    resets_at_to_epoch,
)

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text for readable assertions.

    Args:
        text (str): Text containing ANSI escape codes.

    Returns:
        str: Plain text with ANSI codes removed.
    """
    return ANSI_RE.sub("", text)


def test_parse_model_and_effort() -> None:
    """Verify model display_name, id fallback, and nullable effort parsing."""
    data = parse_status_data(
        {
            "model": {
                "id": "gemini-4-argon",
                "display_name": "Gemini 4 Argon",
                "effort": "medium",
            }
        }
    )
    assert data.model_name == "Gemini 4 Argon"
    assert data.model_id == "gemini-4-argon"
    assert data.effort == "medium"

    data_null_effort = parse_status_data(
        {
            "model": {
                "id": "gemini-3-pro",
                "effort": None,
            }
        }
    )
    assert data_null_effort.model_name == "gemini-3-pro"
    assert data_null_effort.effort == ""

    data_empty = parse_status_data({})
    assert data_empty.model_name == "?"
    assert data_empty.cwd == "."


def test_quota_bucket_selection_argon() -> None:
    """Verify Gemini 4 Argon selects gemini-5h and gemini-argon-wtu-weekly."""
    payload = {
        "model": {"id": "gemini-4-argon", "display_name": "Gemini 4 Argon"},
        "quota": {
            "gemini-5h": {"remaining_fraction": 0.82, "reset_in_seconds": 3900},
            "gemini-weekly": {"remaining_fraction": 0.90, "reset_in_seconds": 86400},
            "gemini-argon-wtu-weekly": {
                "remaining_fraction": 0.65,
                "reset_time": "2026-11-20T00:00:00Z",
            },
            "3p-5h": {"remaining_fraction": 0.10},
        },
    }
    data = parse_status_data(payload)
    assert data.five_hour is not None
    assert round(data.five_hour.used_percentage or 0.0, 2) == 18.0
    assert data.five_hour.reset_in_seconds == 3900

    assert data.seven_day is not None
    assert round(data.seven_day.used_percentage or 0.0, 2) == 35.0
    assert data.seven_day.resets_at == "2026-11-20T00:00:00Z"


def test_quota_bucket_selection_argon_fallback_when_wtu_disabled() -> None:
    """Verify Argon falls back to gemini-weekly if gemini-argon-wtu-weekly is disabled."""
    payload = {
        "model": {"id": "gemini-4-argon"},
        "quota": {
            "gemini-5h": {"remaining_fraction": 0.5},
            "gemini-argon-wtu-weekly": {"remaining_fraction": 0.1, "disabled": True},
            "gemini-weekly": {"remaining_fraction": 0.75, "reset_in_seconds": 7200},
        },
    }
    data = parse_status_data(payload)
    assert data.seven_day is not None
    assert round(data.seven_day.used_percentage or 0.0, 2) == 25.0
    assert data.seven_day.reset_in_seconds == 7200


def test_quota_bucket_selection_gemini_and_3p() -> None:
    """Verify standard Gemini and third-party (Claude/GPT) quota bucket selection."""
    quota = {
        "gemini-5h": {"remaining_fraction": 0.9},
        "gemini-weekly": {"remaining_fraction": 0.8},
        "3p-5h": {"remaining_fraction": 0.4},
        "3p-weekly": {"remaining_fraction": 0.2},
    }
    gemini_data = parse_status_data({"model": {"id": "gemini-3-flash"}, "quota": quota})
    assert gemini_data.five_hour is not None
    assert round(gemini_data.five_hour.used_percentage or 0.0, 2) == 10.0
    assert gemini_data.seven_day is not None
    assert round(gemini_data.seven_day.used_percentage or 0.0, 2) == 20.0

    claude_data = parse_status_data({"model": {"id": "claude-sonnet-4"}, "quota": quota})
    assert claude_data.five_hour is not None
    assert round(claude_data.five_hour.used_percentage or 0.0, 2) == 60.0
    assert claude_data.seven_day is not None
    assert round(claude_data.seven_day.used_percentage or 0.0, 2) == 80.0


def test_quota_disabled_and_none_remaining() -> None:
    """Verify disabled buckets and null remaining_fraction are ignored."""
    payload = {
        "model": {"id": "gemini-3-pro"},
        "quota": {
            "gemini-5h": {"remaining_fraction": None},
            "gemini-weekly": {"remaining_fraction": 0.5, "disabled": True},
        },
    }
    data = parse_status_data(payload)
    assert data.five_hour is None
    assert data.seven_day is None


def test_context_usage_and_total_tokens_fallback() -> None:
    """Verify current_usage parsing and fallback to total_input/output_tokens."""
    data_with_usage = parse_status_data(
        {
            "context_window": {
                "used_percentage": 42.5,
                "current_usage": {
                    "input_tokens": 1200,
                    "output_tokens": 350,
                    "cache_creation_input_tokens": 500,
                    "cache_read_input_tokens": 0,
                },
            }
        }
    )
    rendered = strip_ansi(tokens_str(data_with_usage, DARK_THEME))
    assert rendered == "in:1.2k out:350 cw:500"

    data_fallback = parse_status_data(
        {
            "context_window": {
                "used_percentage": 10.0,
                "current_usage": None,
                "total_input_tokens": 150000,
                "total_output_tokens": 2500,
            }
        }
    )
    rendered_fallback = strip_ansi(tokens_str(data_fallback, DARK_THEME))
    assert rendered_fallback == "in:150k out:2.5k"


def test_context_bar_warning_badge() -> None:
    """Verify context bar renders 16 segments and >=90% warning badge."""
    ok_bar = strip_ansi(context_bar_str(50.0, DARK_THEME))
    assert "50%" in ok_bar
    assert ICON_WARN not in ok_bar
    assert ok_bar.count("█") + ok_bar.count("░") == 16

    warn_bar = strip_ansi(context_bar_str(92.0, DARK_THEME))
    assert "92%" in warn_bar
    assert ICON_WARN in warn_bar


def test_usage_segment_countdown_sources() -> None:
    """Verify countdown formatting from reset_in_seconds and ISO reset_time."""
    win_sec = RateLimitWindow(used_percentage=18.0, reset_in_seconds=8100)
    assert strip_ansi(usage_segment_str("5h", win_sec, DARK_THEME)) == "5h 18% (2h15m)"

    now_epoch = resets_at_to_epoch("2026-11-14T10:00:00Z")
    assert now_epoch is not None
    win_iso = RateLimitWindow(used_percentage=75.0, resets_at="2026-11-14T11:30:00Z")
    assert strip_ansi(usage_segment_str("5h", win_iso, DARK_THEME, now=now_epoch)) == "5h 75% (1h30m)"


def test_git_info_str_subprocess_and_fallback() -> None:
    """Verify git subprocess parsing (+staged ~unstaged ?untracked) and vcs fallback."""
    dirty_proc = MagicMock(
        returncode=0,
        stdout="## main...origin/main\nM  a.py\n M b.py\n?? c.py\n",
    )
    with patch("agy_statusline.formatters.subprocess.run", return_value=dirty_proc):
        out = strip_ansi(git_info_str("/tmp/repo", DARK_THEME))
        assert "+1" in out
        assert "~1" in out
        assert "?1" in out
        assert "main" in out

    clean_proc = MagicMock(returncode=0, stdout="## feature/xyz...origin/feature/xyz\n")
    with patch("agy_statusline.formatters.subprocess.run", return_value=clean_proc):
        out_clean = strip_ansi(git_info_str("/tmp/repo", DARK_THEME))
        assert out_clean.endswith("feature/xyz")

    with patch("agy_statusline.formatters.subprocess.run", side_effect=subprocess.SubprocessError("fail")):
        out_fb = strip_ansi(git_info_str("/tmp/repo", DARK_THEME, fallback_branch="dev", fallback_dirty=True))
        assert "dev*" in out_fb


def test_build_lines_and_render_statusline() -> None:
    """Verify full two-line output structure and omission of cost."""
    payload = {
        "model": {"id": "gemini-4-argon", "display_name": "Gemini 4 Argon", "effort": "medium"},
        "workspace": {"current_dir": "/home/user/projects/agy-cli"},
        "context_window": {
            "used_percentage": 25.0,
            "current_usage": {"input_tokens": 2000, "output_tokens": 400},
        },
        "quota": {
            "gemini-5h": {"remaining_fraction": 0.8, "reset_in_seconds": 3600},
            "gemini-argon-wtu-weekly": {"remaining_fraction": 0.9, "reset_in_seconds": 172800},
        },
        "vim": {"mode": "NORMAL"},
    }
    with patch("agy_statusline.formatters.subprocess.run", side_effect=OSError("no git")):
        output = strip_ansi(render_statusline(json.dumps(payload)))

    lines = output.splitlines()
    assert len(lines) == 2
    assert "Gemini 4 Argon (medium)" in lines[0]
    assert "25%" in lines[0]
    assert "in:2.0k out:400" in lines[0]
    assert "$" not in lines[0]

    assert "5h 20% (1h)" in lines[1]
    assert "7d 10% (2d0h)" in lines[1]
    assert "NORMAL" in lines[1]


def test_theme_detection_and_helpers() -> None:
    """Verify theme detection via STATUSLINE_THEME, COLORFGBG, and pct_color thresholds."""
    assert detect_theme({"STATUSLINE_THEME": "light"}) == "light"
    assert detect_theme({"STATUSLINE_THEME": "DARK"}) == "dark"
    assert detect_theme({"COLORFGBG": "0;15"}) == "light"
    assert detect_theme({"COLORFGBG": "15;0"}) == "dark"
    assert detect_theme({}) == "dark"

    assert build_theme("light") == LIGHT_THEME
    assert build_theme("dark") == DARK_THEME

    assert pct_color(20.0, DARK_THEME) == DARK_THEME.green
    assert pct_color(75.0, DARK_THEME) == DARK_THEME.yellow
    assert pct_color(95.0, DARK_THEME) == DARK_THEME.red


def test_format_helpers() -> None:
    """Verify token, countdown, and directory shortening helpers."""
    assert format_tokens(500) == "500"
    assert format_tokens(1500) == "1.5k"
    assert format_tokens(150_000) == "150k"
    assert format_tokens(2_500_000) == "2.5M"

    assert format_countdown(0) == "0m"
    assert format_countdown(300) == "5m"
    assert format_countdown(3660) == "1h01m"
    assert format_countdown(90000) == "1d1h"

    assert shorten_dir("/home/alice/a/b", home="/home/alice") == "~/a/b"
    assert shorten_dir("/home/alice/a/b/c/d", home="/home/alice") == "~/.../c/d"
    assert shorten_dir("/home/alice", home="/home/alice") == "~"

    data = StatusData(model_name="Test", cwd="/tmp")
    line1 = strip_ansi(build_line1(data, DARK_THEME))
    line2 = strip_ansi(build_line2(data, DARK_THEME))
    assert "Test" in line1
    assert "/tmp" in line2


def test_parser_invalid_reset_and_non_finite_floats() -> None:
    """Verify invalid reset_in_seconds stays None and non-finite floats are safely ignored."""
    data = parse_status_data(
        {
            "model": {"id": "gemini-3-pro"},
            "context_window": {
                "used_percentage": float("nan"),
                "context_window_size": float("inf"),
            },
            "quota": {
                "gemini-5h": {
                    "remaining_fraction": 0.5,
                    "reset_in_seconds": "invalid",
                    "reset_time": "2026-11-14T12:00:00Z",
                },
                "gemini-weekly": {
                    "remaining_fraction": float("nan"),
                },
            },
        }
    )
    assert data.used_percentage == 0.0
    assert data.context_window_size == 0
    assert data.five_hour is not None
    assert data.five_hour.reset_in_seconds is None
    assert data.five_hour.resets_at == "2026-11-14T12:00:00Z"
    assert data.seven_day is None
