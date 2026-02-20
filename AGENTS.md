# Agent Continuity Guide

## Source Reference
- **Reference Project**: \`mcp-ssh-session\`
- **Absolute Path**: \`/home/jon/Dev/ai/mcp/mcp-ssh-session\`
- **Purpose**: Port validated logic (SSH Config, Safety Validation) from this path.

## Current Infrastructure
- Environment manager: \`uv\`
- Command runner: \`just\` (see \`Justfile\`)
- Core library: \`libtmux\`
- Logic: \`mcp_ssh_tmux/session_manager.py\` and \`server.py\` are scaffolded.

## Roadmap & Task List

### Phase 1: Porting (Priority: High)
- [x] **Port SSH Config Logic**: Bring \`_load_ssh_config\` and \`_resolve_connection\` (implemented via \`ssh -G\`) into \`session_manager.py\`.
- [x] **Port Safety Validation**: Bring the \`CommandValidator\` from \`validation.py\` into this project to prevent dangerous commands.

### Phase 2: Refinement
- [x] **ANSI Sanitization**: Implement logic to strip complex ANSI escape codes so the LLM gets clean text snapshots.
- [x] **Prompt Detection Hints**: Add an optional utility that looks for common prompt characters (\$, #, >) at the end of snapshots to "help" the LLM know when output is settled.
- [x] **Window Renaming**: Update window titles to reflect the host/user for easier human debugging via \`tmux attach\`.

### Phase 3: Advanced
- [x] **File Transfer**: Added \`read_remote_file\` and \`write_remote_file\` tools using shell-based capture/transfer over existing sessions.
- [ ] **Streaming Status**: Implement a mechanism to stream live terminal updates via MCP resources.

## Quick Start for the Next Agent
1. Read \`SPEC.md\` to understand the architecture.
2. Run \`just install\` to set up the environment.
3. Use the available tools to manage SSH sessions via tmux.
