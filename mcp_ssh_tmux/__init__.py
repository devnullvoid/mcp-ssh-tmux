"""Package initialization and platform compatibility defaults."""

import os
import sys

# Configure this before importing libtmux: its format separator is read once
# at import time. Native Windows tmux can replace the default Unicode U+241E
# separator with '?', causing libtmux's strict field parsing to fail.
if sys.platform == "win32":
    os.environ.setdefault("LIBTMUX_TMUX_FORMAT_SEPARATOR", "|__LIBTMUX_SEP__|")
