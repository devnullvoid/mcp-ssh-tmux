# mcp-ssh-tmux

A high-performance, persistent Model Context Protocol (MCP) server that manages SSH sessions via a local `tmux` instance.

## Why this exists?

Traditional SSH automation runs individual commands without state tracking between executions. Other implementations rely on complex regex patterns to detect command completion. By using `tmux` as a persistent terminal multiplexer, this project eliminates that complexity entirely. The AI agent simply "looks" at the screen like a human would - the server provides visual snapshots, and the agent interprets prompts, errors, and output naturally.

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
-   `send_keys(session_id, keys)`: Sends raw keystrokes without Enter. Use for Ctrl+C, Ctrl+D, interactive input, etc.
-   `get_snapshot(session_id, lines)`: Captures the current screen state.
-   `read_remote_file(session_id, remote_path)`: Efficiently reads a remote file.
-   `write_remote_file(session_id, remote_path, content, append)`: Writes content to a remote file.
-   `list_sessions()`: Lists all active SSH windows.
-   `close_session(session_id)`: Kills the window and cleans up. **WARNING**: This terminates any running processes in the session. For long-running tasks, leave the session open and monitor with `get_snapshot()`.

## Important Notes

### Session Management

- **Do not close sessions with active processes**: Closing a session terminates all running commands (builds, downloads, etc.)
- **Monitor long-running tasks**: Use `get_snapshot()` to check progress without closing the session
- **Sessions persist**: SSH connections remain alive in tmux even if the MCP server restarts
- **Manual inspection**: Run `tmux attach -t mcp-ssh` to see what's happening in real-time

## License

MIT
