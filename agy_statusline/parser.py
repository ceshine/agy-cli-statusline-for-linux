"""Parser for Antigravity CLI (agy) stdin JSON payloads."""

import math
from typing import Any

from agy_statusline.models import StatusData, CurrentUsage, RateLimitWindow


def _as_dict(value: Any) -> dict[str, Any]:
    """Return value if it is a dict, otherwise an empty dict.

    Args:
        value (Any): Candidate mapping value.

    Returns:
        dict[str, Any]: The original dict or an empty dict.
    """
    return value if isinstance(value, dict) else {}


def _as_optional_int(value: Any) -> int | None:
    """Safely convert a value to int, returning ``None`` on failure.

    Args:
        value (Any): Value to convert.

    Returns:
        int | None: Converted integer, or ``None`` if conversion fails.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except TypeError, ValueError, OverflowError:
        return None


def _as_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to int, returning default on failure.

    Args:
        value (Any): Value to convert.
        default (int): Fallback integer if conversion fails.

    Returns:
        int: Converted integer or default.
    """
    parsed = _as_optional_int(value)
    return default if parsed is None else parsed


def _as_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to a finite float, returning default on failure.

    Args:
        value (Any): Value to convert.
        default (float): Fallback float if conversion fails or value is non-finite.

    Returns:
        float: Converted finite float or default.
    """
    if value is None or isinstance(value, bool):
        return default
    try:
        parsed = float(value)
    except TypeError, ValueError:
        return default
    return parsed if math.isfinite(parsed) else default


def _clamp_pct(pct: float) -> float:
    """Clamp a percentage value to the inclusive range [0.0, 100.0].

    Args:
        pct (float): Raw percentage value.

    Returns:
        float: Clamped percentage value, or ``0.0`` if ``pct`` is non-finite.
    """
    if not math.isfinite(pct):
        return 0.0
    return max(0.0, min(100.0, pct))


def _select_quota_bucket(quota: dict[str, Any], candidate_keys: list[str]) -> RateLimitWindow | None:
    """Select the first active quota bucket matching candidate_keys.

    Ignores buckets that are missing, not dicts, marked ``disabled: True``,
    or missing ``remaining_fraction``.

    Args:
        quota (dict[str, Any]): Mapping of quota bucket IDs to bucket objects.
        candidate_keys (list[str]): Ordered list of bucket IDs to check.

    Returns:
        RateLimitWindow | None: Parsed rate-limit window, or ``None`` if none active.
    """
    for key in candidate_keys:
        bucket = quota.get(key)
        if not isinstance(bucket, dict):
            continue
        if bucket.get("disabled"):
            continue
        remaining = bucket.get("remaining_fraction")
        if remaining is None or isinstance(remaining, bool):
            continue
        try:
            remaining_val = float(remaining)
        except TypeError, ValueError:
            continue
        if not math.isfinite(remaining_val):
            continue
        used_pct = _clamp_pct((1.0 - remaining_val) * 100.0)

        reset_in_seconds = _as_optional_int(bucket.get("reset_in_seconds"))
        raw_reset_time = bucket.get("reset_time")
        resets_at = str(raw_reset_time) if raw_reset_time else None

        return RateLimitWindow(
            used_percentage=used_pct,
            resets_at=resets_at,
            reset_in_seconds=reset_in_seconds,
        )
    return None


def _parse_rate_limit_fallback(raw_window: Any) -> RateLimitWindow | None:
    """Parse a legacy ``rate_limits`` window object as a fallback.

    Args:
        raw_window (Any): Raw ``rate_limits.five_hour`` or ``rate_limits.seven_day`` object.

    Returns:
        RateLimitWindow | None: Parsed rate-limit window or ``None``.
    """
    if not isinstance(raw_window, dict):
        return None
    used = raw_window.get("used_percentage")
    if used is None:
        return None
    used_pct = _clamp_pct(_as_float(used))
    reset_in_seconds = _as_optional_int(raw_window.get("reset_in_seconds"))
    raw_resets_at = raw_window.get("resets_at") or raw_window.get("reset_time")
    resets_at = str(raw_resets_at) if raw_resets_at else None
    return RateLimitWindow(
        used_percentage=used_pct,
        resets_at=resets_at,
        reset_in_seconds=reset_in_seconds,
    )


def _quota_keys_for_model(model_key: str) -> tuple[list[str], list[str]]:
    """Return ordered (5h_keys, 7d_keys) for the given lowercase model identifier.

    Args:
        model_key (str): Lowercase model ID or display name.

    Returns:
        tuple[list[str], list[str]]: Candidate bucket IDs for 5-hour and 7-day windows.
    """
    if "argon" in model_key:
        return ["gemini-5h"], ["gemini-argon-wtu-weekly", "gemini-weekly"]
    if "gemini" in model_key:
        return ["gemini-5h"], ["gemini-weekly"]
    if "claude" in model_key or "gpt" in model_key:
        return ["3p-5h"], ["3p-weekly"]
    return ["gemini-5h", "3p-5h"], ["gemini-weekly", "gemini-argon-wtu-weekly", "3p-weekly"]


def parse_status_data(payload: dict[str, Any]) -> StatusData:
    """Parse an Antigravity CLI stdin JSON dict into a normalized StatusData.

    Args:
        payload (dict[str, Any]): Deserialized JSON payload from ``agy``.

    Returns:
        StatusData: Normalized status data ready for formatting.
    """
    model = _as_dict(payload.get("model"))
    model_id = str(model.get("id") or "")
    display_name = str(model.get("display_name") or "")
    model_name = display_name or model_id or "?"
    effort = str(model.get("effort") or "")

    workspace = _as_dict(payload.get("workspace"))
    cwd = str(workspace.get("current_dir") or payload.get("cwd") or ".")

    ctx = _as_dict(payload.get("context_window"))
    used_percentage = _clamp_pct(_as_float(ctx.get("used_percentage")))
    context_window_size = _as_int(ctx.get("context_window_size"))

    raw_usage = ctx.get("current_usage")
    current_usage: CurrentUsage | None = None
    if isinstance(raw_usage, dict):
        current_usage = CurrentUsage(
            input_tokens=_as_int(raw_usage.get("input_tokens")),
            output_tokens=_as_int(raw_usage.get("output_tokens")),
            cache_creation_input_tokens=_as_int(raw_usage.get("cache_creation_input_tokens")),
            cache_read_input_tokens=_as_int(raw_usage.get("cache_read_input_tokens")),
        )

    total_input_tokens = _as_int(
        ctx.get("total_input_tokens")
        if ctx.get("total_input_tokens") is not None
        else payload.get("total_input_tokens")
    )
    total_output_tokens = _as_int(
        ctx.get("total_output_tokens")
        if ctx.get("total_output_tokens") is not None
        else payload.get("total_output_tokens")
    )

    quota = _as_dict(payload.get("quota"))
    model_key = (model_id or display_name).lower()
    five_h_keys, seven_d_keys = _quota_keys_for_model(model_key)

    five_hour = _select_quota_bucket(quota, five_h_keys)
    seven_day = _select_quota_bucket(quota, seven_d_keys)

    rate_limits = _as_dict(payload.get("rate_limits"))
    if five_hour is None and rate_limits:
        five_hour = _parse_rate_limit_fallback(rate_limits.get("five_hour"))
    if seven_day is None and rate_limits:
        seven_day = _parse_rate_limit_fallback(rate_limits.get("seven_day"))

    vcs = _as_dict(payload.get("vcs"))
    vcs_branch = str(vcs.get("branch") or "")
    vcs_dirty = bool(vcs.get("dirty") or False)

    vim = _as_dict(payload.get("vim"))
    vim_mode = str(vim.get("mode") or "")

    return StatusData(
        model_name=model_name,
        model_id=model_id,
        effort=effort,
        cwd=cwd,
        used_percentage=used_percentage,
        context_window_size=context_window_size,
        current_usage=current_usage,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        five_hour=five_hour,
        seven_day=seven_day,
        vcs_branch=vcs_branch,
        vcs_dirty=vcs_dirty,
        vim_mode=vim_mode,
    )
