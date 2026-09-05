"""Test platform defaults in fresh processes without starting tmux or SSH."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
ENV_KEY = "LIBTMUX_TMUX_FORMAT_SEPARATOR"


@pytest.mark.parametrize(
    ("platform", "configured", "expected"),
    [
        ("win32", None, "|__LIBTMUX_SEP__|"),
        ("win32", "custom-separator", "custom-separator"),
        ("linux", None, None),
        ("darwin", None, None),
        ("linux", "custom-separator", "custom-separator"),
    ],
)
def test_platform_separator_default(platform, configured, expected):
    env = os.environ.copy()
    env.pop(ENV_KEY, None)
    if configured is not None:
        env[ENV_KEY] = configured
    script = f"""
import os
import sys
sys.platform = {platform!r}
import mcp_ssh_tmux
assert os.environ.get({ENV_KEY!r}) == {expected!r}
"""
    subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, check=True)


def test_windows_separator_survives_lossy_encoding_and_parses():
    env = os.environ.copy()
    env.pop(ENV_KEY, None)
    script = """
import sys
platform = sys.platform
sys.platform = 'win32'
import mcp_ssh_tmux
sys.platform = platform
from libtmux.formats import FORMAT_SEPARATOR
from libtmux.neo import get_output_format, parse_output
from inspect import signature
assert FORMAT_SEPARATOR == '|__LIBTMUX_SEP__|'
for command in ('list-sessions', 'list-windows', 'list-panes'):
    # Older libtmux releases use one format for all listing commands.
    kwargs = {'list_cmd': command, 'tmux_version': '3.6a'} if 'list_cmd' in signature(get_output_format).parameters else {}
    fields, template = get_output_format(**kwargs)
    assert template.encode('ascii', errors='replace').decode('ascii') == template
    values = ['test' if field == 'session_name' else '' for field in fields]
    output = FORMAT_SEPARATOR.join(values) + FORMAT_SEPARATOR
    output = output.encode('ascii', errors='replace').decode('ascii')
    parsed = parse_output(output, **kwargs)
    assert parsed['session_name'] == 'test'
"""
    subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, check=True)
