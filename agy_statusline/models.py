"""Dataclasses representing parsed status line data and color themes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CurrentUsage:
    """Token usage for the current turn/request.

    Attributes:
        input_tokens (int): Number of input tokens.
        output_tokens (int): Number of output tokens.
        cache_creation_input_tokens (int): Tokens written to cache.
        cache_read_input_tokens (int): Tokens read from cache.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass(frozen=True)
class RateLimitWindow:
    """Quota usage and reset timing for a rate-limit window.

    Attributes:
        used_percentage (float | None): Percentage of the quota window used (0-100).
        resets_at (str | None): ISO-8601 reset timestamp string, if provided.
        reset_in_seconds (int | None): Seconds remaining until reset, if provided.
    """

    used_percentage: float | None = None
    resets_at: str | None = None
    reset_in_seconds: int | None = None


@dataclass(frozen=True)
class StatusData:
    """Normalized status payload parsed from Antigravity CLI stdin JSON.

    Attributes:
        model_name (str): Display name (or fallback ID) of the active model.
        model_id (str): Identifier of the active model.
        effort (str): Reasoning effort level (empty string if unset).
        cwd (str): Current working directory path.
        used_percentage (float): Context window usage percentage (0-100).
        context_window_size (int): Maximum context window size in tokens.
        current_usage (CurrentUsage | None): Per-turn token usage, if available.
        total_input_tokens (int): Cumulative session input tokens.
        total_output_tokens (int): Cumulative session output tokens.
        five_hour (RateLimitWindow | None): 5-hour quota window for the active model.
        seven_day (RateLimitWindow | None): 7-day quota window for the active model.
        vcs_branch (str): Fallback VCS branch name from stdin payload.
        vcs_dirty (bool): Fallback VCS dirty flag from stdin payload.
        vim_mode (str): Active Vim/editor mode indicator, if any.
    """

    model_name: str = "?"
    model_id: str = ""
    effort: str = ""
    cwd: str = "."
    used_percentage: float = 0.0
    context_window_size: int = 0
    current_usage: CurrentUsage | None = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    five_hour: RateLimitWindow | None = None
    seven_day: RateLimitWindow | None = None
    vcs_branch: str = ""
    vcs_dirty: bool = False
    vim_mode: str = ""


@dataclass(frozen=True)
class Theme:
    """ANSI color palette for dark or light terminal backgrounds.

    Attributes:
        name (str): Theme name ("dark" or "light").
        fg (str): Default foreground ANSI code.
        dim (str): Dimmed text ANSI code.
        model (str): Model segment ANSI code.
        dir (str): Directory segment ANSI code.
        git (str): Clean git segment ANSI code.
        git_dirty (str): Dirty git segment ANSI code.
        green (str): Healthy usage/quota ANSI code.
        yellow (str): Elevated usage/quota ANSI code.
        red (str): Critical usage/quota ANSI code.
        vim (str): Vim mode indicator ANSI code.
        sep (str): Separator ANSI code.
    """

    name: str
    fg: str
    dim: str
    model: str
    dir: str
    git: str
    git_dirty: str
    green: str
    yellow: str
    red: str
    vim: str
    sep: str
