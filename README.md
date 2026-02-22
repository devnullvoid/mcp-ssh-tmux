# mcp-ssh-tmux

A high-performance, persistent Model Context Protocol (MCP) server that manages SSH sessions via a local `tmux` instance.

## Why this exists?

Unlike traditional SSH automation that relies on complex regex to detect command completion, this project treats the AI agent as a human user who "looks" at the screen. The server provides visual snapshots, and the AI agent interprets the state (prompts, errors, etc.).

## Key Features

-   **Persistence**: SSH connections stay alive in `tmux` even if the MCP server or your AI client restarts.
-   **Observability**: You can manually run `tmux attach -t mcp-ssh` to see exactly what the agent is doing in real-time.
-   **Reliability**: Uses `ssh -G` for robust config resolution (handles aliases, identity files, etc.).
-   **Safety**: Built-in command validation to prevent common dangerous operations.
-   **File Transfer**: Native tools for reading and writing remote files using `cat` and `tee` over the existing PTY.

## Installation

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
-   `send_command(session_id, command, lines)`: Sends a command and polls for a prompt/output.
-   `get_snapshot(session_id, lines)`: Captures the current screen state.
-   `read_remote_file(session_id, remote_path)`: Efficiently reads a remote file.
-   `write_remote_file(session_id, remote_path, content, append)`: Writes content to a remote file.
-   `list_sessions()`: Lists all active SSH windows.
-   `close_session(session_id)`: Kills the window and cleans up.

## License

MIT
