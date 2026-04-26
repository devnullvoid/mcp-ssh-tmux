# mcp-ssh-tmux

[![PyPI version](https://badge.fury.io/py/mcp-ssh-tmux.svg)](https://badge.fury.io/py/mcp-ssh-tmux)
[![Downloads](https://pepy.tech/badge/mcp-ssh-tmux)](https://pepy.tech/project/mcp-ssh-tmux)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/devnullvoid/mcp-ssh-tmux.svg)](https://github.com/devnullvoid/mcp-ssh-tmux/stargazers)

A high-performance, persistent Model Context Protocol (MCP) server that manages SSH sessions via a local `tmux` instance.

## Why this exists?

Traditional SSH automation runs individual commands without state tracking between executions. Other implementations rely on complex regex patterns to detect command completion. By using `tmux` as a persistent terminal multiplexer, this project eliminates that complexity entirely. The AI agent simply "looks" at the screen like a human would - the server provides visual snapshots, and the agent interprets prompts, errors, and output naturally.

## Key Features

-   **Persistence**: SSH connections stay alive in `tmux` even if the MCP server or your AI client restarts.
-   **Observability**: You can manually run `tmux attach -t mcp-ssh` to see exactly what the agent is doing in real-time.
-   **Reliability**: Uses `ssh -G` for robust config resolution (handles aliases, identity files, etc.).
-   **Safety**: Built-in command validation to prevent common dangerous operations.
-   **File Transfer**: Native tools for reading and writing remote files. Reads prefer a full-file SSH transfer and fall back to the existing PTY when needed.

## Installation

### Requirements

-   **tmux** must be installed on your system
    -   Ubuntu/Debian: `apt install tmux`
    -   macOS: `brew install tmux`
    -   Arch: `pacman -S tmux`

### Via `uv` (Recommended)

```bash
uv tool install mcp-ssh-tmux
```

### Via `pip`

```bash
pip install mcp-ssh-tmux
```

## Configuration

Add this to your `mcp.json` (e.g., in Claude Desktop, Cursor, or 1mcp):

```json
{
  "mcpServers": {
    "ssh-tmux": {
      "command": "uv",
      "args": [
        "run",
        "mcp-ssh-tmux"
      ]
    }
  }
}
```

*Note: If you installed via `uv tool install`, you can just use `mcp-ssh-tmux` as the command.*

## Tools

-   `open_session(host, username, port)`: Opens a new SSH connection in a unique tmux window.
-   `send_command(session_id, command, lines, timeout)`: Sends a command and polls for a prompt/output. Returns only the last `lines` of terminal output/scrollback. `timeout` (default 2.0s) controls how long to wait — increase for slower commands like package installs.
-   `send_keys(session_id, keys)`: Sends raw keystrokes without Enter. Use for Ctrl+C, Ctrl+D, interactive input, etc.
-   `get_snapshot(session_id, lines)`: Captures the current screen state. Returns only the last `lines` of terminal output/scrollback.
-   `read_remote_file(session_id, remote_path, fallback_lines)`: Reads a remote text file. Prefer this over `cat` via `send_command()` when you need the full file contents. `fallback_lines` controls bounded tmux-history capture if direct SSH read is unavailable.
-   `write_remote_file(session_id, remote_path, content, append)`: Writes content to a remote file.
-   `list_sessions()`: Lists all active SSH windows.
-   `close_session(session_id)`: Kills the window and cleans up. **WARNING**: This terminates any running processes in the session. For long-running tasks, leave the session open and monitor with `get_snapshot()`.

## Important Notes

### Reading Files

- **Use `read_remote_file()` for file contents**: `send_command("cat ...")` and `get_snapshot()` are screen/snapshot tools, so they only return the tail of terminal output.
- **`lines` controls snapshot depth**: Increase `lines` on `send_command()` or `get_snapshot()` when you need more terminal history, but use `read_remote_file()` for actual file reads.
- **`fallback_lines` controls PTY fallback depth**: If direct SSH file read is unavailable, `read_remote_file()` inspects only the last `fallback_lines` of tmux history. Increase it when needed, but keep it bounded.
- **Best for text files**: `read_remote_file()` is intended for configs, source, logs, and similar text content.

### Session Management

- **Do not close sessions with active processes**: Closing a session terminates all running commands (builds, downloads, etc.)
- **Monitor long-running tasks**: Use `get_snapshot()` to check progress without closing the session
- **Sessions persist**: SSH connections remain alive in tmux even if the MCP server restarts
- **Manual inspection**: Run `tmux attach -t mcp-ssh` to see what's happening in real-time

## Acknowledgments

Built with [FastMCP](https://github.com/PrefectHQ/fastmcp) and [libtmux](https://github.com/tmux-python/libtmux).

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## Star History

If you find this project useful, please consider giving it a star! ⭐

## License

MIT
