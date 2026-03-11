install:
    uv sync

test:
    uv run --active pytest -v -s

run:
    uv run --active mcp-ssh-tmux

dev:
    uv run --active python -m mcp_ssh_tmux.server

release version:
    #!/usr/bin/env bash
    set -euo pipefail
    # Validate version format
    if [[ ! "{{version}}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "Error: Version must be in format v#.#.# (e.g., v0.1.1)"
        exit 1
    fi
    new_version="{{version}}"
    new_version="${new_version#v}"
    # Update pyproject.toml
    sed -i "s/^version = .*/version = \"$new_version\"/" pyproject.toml
    # Verify the update worked
    if ! grep -q "^version = \"$new_version\"$" pyproject.toml; then
        echo "Error: Failed to update version in pyproject.toml"
        exit 1
    fi
    # Commit, tag, and push
    git add pyproject.toml
    git commit -m "chore: bump version to $new_version"
    git push
    git tag -a {{version}} -m "Release {{version}}"
    git push origin {{version}}
