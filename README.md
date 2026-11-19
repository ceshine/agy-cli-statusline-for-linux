# `agy-cli-statusline-for-linux`

A fast, zero-dependency Python status line for the Google Antigravity CLI (`agy`), adapted from [claude-statusline-for-linux](https://github.com/ceshine/claude-statusline-for-linux).

> **Note:** This tool primarily targets Linux. Compatibility with macOS and Windows is unverified.

## Features

- **Two-line ANSI status output** using Material Design Nerd Font icons:
  - **Line 1:** `Model (+ Effort) │ Context Bar (16 segments, >=90% warning) │ Tokens (in/out/cw/cr)`
  - **Line 2:** `Directory │ Git Branch & Status (+staged ~unstaged ?untracked) │ 5h Quota │ 7d Quota │ Vim Mode`
- **Active-model quota matching:** Automatically selects the right `5h` and `7d` quota buckets (`gemini-5h`, `gemini-weekly`, `gemini-argon-wtu-weekly`, `3p-5h`, `3p-weekly`) for the active model.
- **Automatic dark/light theme detection:** Supports `STATUSLINE_THEME` (`dark` / `light`) and `COLORFGBG`.
- **Zero runtime dependencies:** Stdlib-only Python (`>=3.14`) for fast execution.

## Prerequisites

- **Linux**
- **Python 3.14+**
- **[uv](https://docs.astral.sh/uv/)** installed
- **`git`** (optional, for detailed repository status counts)
- **A Nerd Font** (for Material Design icons; otherwise icons may render as empty boxes)
- **Google Antigravity CLI (`agy`)** with status line support

## Installation

1. Install the tool with `uv`:

```bash
uv tool install git+https://github.com/ceshine/agy-cli-statusline-for-linux.git
```

Make sure `uv`'s tool bin directory (typically `~/.local/bin`) is on your `PATH` (you can run `uv tool update-shell` if needed), or use the full path `~/.local/bin/agy-statusline` below.

2. Add or update the `statusLine` setting in `~/.gemini/antigravity-cli/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "agy-statusline"
  }
}
```

> **Why `uv tool install` instead of `uvx`?** Running `uvx --from git+...` with an unpinned Git URL checks GitHub for updates on invocation, which adds network latency and can sporadically trigger `agy` statusline timeouts (`signal: killed`). Installing the tool locally avoids network checks and keeps startup fast.

You can also toggle or configure the status line interactively inside `agy` using the `/statusline` slash command.

### Update

Run the following command to update the installed tool to the latest commit on GitHub:

```bash
uv tool upgrade --reinstall agy-cli-statusline-for-linux
```

> **Note:** `--reinstall` implies `--refresh`, ensuring `uv` fetches and rebuilds from the latest commit even if the package version number has not changed.

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
