# `agy-cli-statusline-for-linux`

A fast, zero-dependency Linux-first Python status line for the Google Antigravity CLI (`agy`), adapted from [claude-statusline-for-linux](https://github.com/ceshine/claude-statusline-for-linux).

## Features

- **Two-line ANSI status output** using Material Design Nerd Font icons:
  - **Line 1:** `Model (+ Effort) │ Context Bar (16 segments, >=90% warning) │ Tokens (in/out/cw/cr)`
  - **Line 2:** `Directory │ Git Branch & Status (+staged ~unstaged ?untracked) │ 5h Quota │ 7d Quota │ Vim Mode`
- **Active-model quota matching:** Automatically selects the right `5h` and `7d` quota buckets (`gemini-5h`, `gemini-weekly`, `gemini-argon-wtu-weekly`, `3p-5h`, `3p-weekly`) for the active model.
- **Automatic dark/light theme detection:** Supports `STATUSLINE_THEME` (`dark` / `light`) and `COLORFGBG`.
- **Zero runtime dependencies:** Stdlib-only Python (`>=3.14`) for fast execution.

## Prerequisites

- **Python 3.14+**
- **[uv](https://docs.astral.sh/uv/)**
- **`git`** (optional, for detailed repository status counts)
- **A Nerd Font** (for Material Design icons)

## Installation

Install the CLI globally or into a tool environment using `uv`:

```bash
uv tool install .
```

Or run directly from the repository with `uv run`:

```bash
uv run agy-statusline
```

## Configuration in Antigravity CLI (`agy`)

Add or update the `statusLine` setting in `~/.gemini/antigravity-cli/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "agy-statusline"
  }
}
```

If you didn't install it via `uv tool install`, point `command` to `uv run --directory /path/to/agy-cli-statusline-for-linux agy-statusline`.

You can also toggle or configure the status line interactively inside `agy` using the `/statusline` slash command.

## Environment Variables

- `STATUSLINE_THEME`: Force `"dark"` or `"light"` theme.
- `COLORFGBG`: Used as a fallback to detect light vs. dark terminal backgrounds.

## Development

```bash
uv sync
uv run pytest
uvx ruff check .
uvx ruff format --check --line-length 120 .
```
