install:
    uv sync

test:
    uv run --active pytest -v -s

run:
    uv run --active mcp-ssh-tmux

dev:
    uv run --active python -m mcp_ssh_tmux.server

release version:
    git tag -a v{{version}} -m "Release v{{version}}"
    git push origin v{{version}}
