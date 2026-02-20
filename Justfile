install:
    uv sync

test:
    uv run --active pytest -v -s

run:
    uv run --active mcp-ssh-tmux

dev:
    uv run --active python -m mcp_ssh_tmux.server
