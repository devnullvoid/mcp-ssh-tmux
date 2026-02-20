# Technical Specification: mcp-ssh-tmux

## Overview
A high-performance, persistent MCP server that manages SSH sessions via a local \`tmux\` instance.

## Philosophy: LLM-as-Observer
Unlike traditional SSH automation that relies on complex regex to detect command completion, this project treats the AI agent as a human user who "looks" at the screen. The server is responsible for:
1. Sending keystrokes to a PTY.
2. Capturing visual snapshots of the PTY.
3. Managing the lifecycle of the local \`tmux\` windows.

The AI Agent is responsible for:
1. Determining if a command is finished.
2. Handling unexpected prompts (passwords, [Y/n] questions).
3. Interpreting error messages.

## Internal State
- **tmux Session Name**: \`mcp-ssh\`
- **Window Management**: Each window is named with a unique ID (\`ssh-<short-uuid>\`).
- **Persistence**: If the MCP server dies, \`tmux\` keeps the SSH connections open. Re-opening the MCP server allows the agent to re-attach to existing windows.

## Tool Definitions
- \`open_session(host, username, port)\`: Creates a window, runs \`ssh\`, returns initial text.
- \`send_command(session_id, command)\`: Sends keys + Enter, waits briefly, returns screen text.
- \`get_snapshot(session_id)\`: Returns current screen text without sending keys.
- \`list_sessions()\`: Returns active window IDs.
- \`close_session(session_id)\`: Kills the tmux window.
