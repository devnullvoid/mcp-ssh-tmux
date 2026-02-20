install:
    uv pip install -e .

test:
    pytest

run:
    uv run mcp-ssh-tmux

dev:
    uv run python -m mcp_ssh_tmux.server
