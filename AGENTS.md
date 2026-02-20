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

### Connection Management
- **SSH Execution**: We start `ssh` directly as the `window_shell` command in tmux. This is more reliable than starting a shell and sending keys.
- **Config Resolution**: We use `ssh -G <host>` to resolve aliases and identity files from the user's `~/.ssh/config`.
- **BatchMode**: We intentionally avoided `BatchMode=yes` to allow the AI to handle interactive password/passphrase prompts visually.
- **Persistence**: `remain-on-exit` is enabled via `window.set_option("remain-on-exit", "on")`. This allows capturing final errors after a connection dies.

### Session Lifecycle
- **Cleanup**: 
    - The default "0" window is killed upon the first SSH connection to ensure the session can close fully when done.
    - `TmuxSessionManager.close_window` kills the entire tmux session if the last active SSH window is closed.
- **Lazy Init**: `server.py` uses `get_manager()` for lazy initialization to avoid creating empty tmux sessions on server startup.

### File Operations
- **Method**: Uses `cat` and `tee` over the existing PTY.
- **Reliability**: Uses unique markers (`__MCP_EOF_<uuid>__`) and base64 encoding to handle binary data and special characters without shell escaping issues.
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
- [ ] **Multi-Pane Layouts**: Add tool to split windows for side-by-side monitoring (e.g., `tail -f` in one pane, interactive shell in another).
- [ ] **Port Forwarding**: Add tools to manage SSH tunnels via the same tmux background process.
- [ ] **Session Re-attachment**: Improve `list_sessions` to allow re-associating with tmux windows created in previous server runs.

## Quick Start
1. `just install`
2. `just test` (Runs all 15+ tests)
3. `mcp-ssh-tmux` (Start the server)
