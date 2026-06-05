# Agent Continuity Guide

## Source Reference
- **Reference Project**: `mcp-ssh-session`
- **Absolute Path**: `/home/jon/Dev/ai/mcp/mcp-ssh-session`
- **Status**: Pivot complete. Logic ported and improved.

## Current Infrastructure
- **Environment**: `uv` (Python 3.14+)
- **Command Runner**: `just` (see `Justfile`)
- **Core Library**: `libtmux` (v0.30+ API used)
- **Logic**: `mcp_ssh_tmux/session_manager.py` and `server.py`.

## Technical Insights for Future Agents

### Philosophy: LLM-as-Observer
- The server provides raw visual snapshots. The AI agent is responsible for interpreting state (prompts, errors, etc.).
- **Hints**: `server.py` appends `[INFO: ...]` hints to snapshots when common shell prompts or password requests are detected.

### Async Polling (Critical)
- **`send_command` and `read_file` MUST use `await asyncio.sleep()`, never `time.sleep()`**. The MCP server runs on an async event loop (FastMCP/uvicorn). Synchronous sleep blocks the entire event loop, making the server unresponsive to all other requests during the polling period. This was the root cause of a production bug where `send_command` with large timeouts (e.g., 60s for `docker service update`) killed the server's ability to handle concurrent `get_snapshot` or `list_sessions` calls.

### Key Dispatch
- **`send_keys` (literal mode)** uses `pane.cmd("send-keys", *keys.split())` to pass each token as a separate tmux argument. This lets tmux interpret key names (`Enter`, `C-c`, `Tab`) while still sending unrecognized tokens as literal text.
- **Do NOT use libtmux's `literal=True`** — it passes `-l` to tmux, which disables all key name interpretation (e.g., `"yes Enter"` would type the word "Enter").

### Connection Management
- **SSH Execution**: We start `ssh` directly as the `window_shell` command in tmux. This is more reliable than starting a shell and sending keys.
- **Config Resolution**: We use `ssh -G <host>` to resolve aliases and identity files from the user's `~/.ssh/config`.
- **Interactive Sessions**: We intentionally avoid `BatchMode=yes` for the primary tmux-backed SSH session so the AI can handle interactive password/passphrase prompts visually.
- **Direct File Reads**: `read_remote_file` first attempts a separate non-interactive `ssh -o BatchMode=yes ... cat -- <path>` using the resolved host/user/port/key info. If that fails, it falls back to bounded tmux history capture.
- **Persistence**: `remain-on-exit` is enabled via `window.set_option("remain-on-exit", "on")`. This allows capturing final errors after a connection dies.

### Session Lifecycle
- **Cleanup**: 
    - The default "0" window is killed upon the first SSH connection to ensure the session can close fully when done.
    - `TmuxSessionManager.close_window` kills the entire tmux session if the last active SSH window is closed.
    - **Dead Session Reaper**: A background task (started via FastMCP `lifespan`) automatically kills sessions that have been dead (disconnected) for >24 hours.
    - **Manual Cleanup**: The `cleanup_dead_sessions` tool allows bulk purging of dead sessions. `TmuxSessionManager` tracks death timestamps in memory (`_dead_since`) to support age-based filtering.
- **Lazy Init**: `server.py` uses `get_manager()` for lazy initialization to avoid creating empty tmux sessions on server startup.

### Transports
- **Default**: The server defaults to `stdio` for standard MCP pipes.
- **Streamable HTTP**: Support for the modern MCP HTTP standard is implemented via `FastMCP`. 
    - Setting `FASTMCP_TRANSPORT=http` (or `streamable-http`) triggers the `uvicorn`-backed server.
    - The `run()` function in `server.py` maps these environment variables to the `mcp.run()` call.
    - Legacy `sse` is still supported but discouraged in favor of the unified `/mcp` endpoint.

### File Operations
- **Read Path**: `read_remote_file` prefers a direct SSH exec for full-file reads and falls back to `cat` over the existing PTY only when necessary.
- **Fallback Bound**: PTY fallback is intentionally bounded via `fallback_lines` to avoid dumping an entire long-lived tmux history into model context.
- **Write Path**: `write_remote_file` uses `tee` over the existing PTY with base64 encoding.
- **Reliability**: PTY reads use unique markers (`__MCP_EOF_<uuid>__`), and writes use base64 encoding to handle special characters without fragile shell escaping.
- **History**: Commands are prefixed with a leading space to trigger `HISTCONTROL=ignorespace` and keep capture noise out of the user's shell history.

### Testing
- **Unit Tests**: `tests/test_session_manager.py` and `tests/test_validation.py`. Always use the `mock_tmux` fixture to avoid orphaned real sessions.
- **Live Tests**: `tests/test_live_ssh.py` tests against `localhost`. 
- **E2E**: Verified against MikroTik (RouterOS) and Debian 13 (Proxmox) environments.

## Roadmap & Task List

### Phase 1 & 2: Complete
- [x] Port SSH Config & Safety Validation.
- [x] ANSI Sanitization & Prompt Hints.
- [x] Robust Window Renaming (user@host-id).

### Phase 3: Advanced & Beyond
- [x] **File Transfer**: `read_remote_file` and `write_remote_file` implemented.
- [x] **Streaming Status**: `ssh-tmux://{session_id}/snapshot` MCP resource implemented.
- [x] **PyPI Release**: v0.1.0 published.
- [x] **Cleanup Tools**: `cleanup_dead_sessions` and background reaper (lifespan) implemented.
- [x] **HTTP Transport**: Support for the modern `streamable-http` transport implemented.
- [ ] **Multi-Pane Layouts**: Add tool to split windows for side-by-side monitoring (e.g., `tail -f` in one pane, interactive shell in another).
- [ ] **Port Forwarding**: Add tools to manage SSH tunnels via the same tmux background process.
- [ ] **Session Re-attachment**: Improve `list_sessions` to allow re-associating with tmux windows created in previous server runs.

## Quick Start
1. `just install`
2. `just test` (Runs the full test suite)
3. `mcp-ssh-tmux` (Start the server)
