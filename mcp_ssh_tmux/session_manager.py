import os
import libtmux
import uuid
import subprocess
import re
from typing import Optional, List, Dict, Any
from pathlib import Path
from .validation import CommandValidator

class TmuxSessionManager:
    def __init__(self, session_name: str = "mcp-ssh"):
        self.session_name = session_name
        self.server = libtmux.Server()
        self._session = None
        self.command_validator = CommandValidator()

    @property
    def session(self):
        """Property that ensures the tmux session is alive and returns it."""
        session = self.server.sessions.get(session_name=self.session_name, default=None)
        if not session:
            session = self.server.new_session(session_name=self.session_name)
        self._session = session
        return self._session

    def _resolve_connection(self, host: str) -> Dict[str, str]:
        """Resolve SSH connection parameters using ssh -G."""
        try:
            result = subprocess.run(
                ["ssh", "-G", host],
                capture_output=True,
                text=True,
                check=True
            )
            config = {}
            for line in result.stdout.splitlines():
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    config[parts[0].lower()] = parts[1]
            return config
        except subprocess.CalledProcessError:
            return {"hostname": host}

    def open_ssh(self, host: str, username: Optional[str] = None, port: Optional[int] = None) -> str:
        """Open a new SSH connection in a new tmux window."""
        config = self._resolve_connection(host)
        
        resolved_host = config.get("hostname", host)
        resolved_user = username or config.get("user")
        resolved_port = port or config.get("port")
        resolved_key = config.get("identityfile")

        short_id = uuid.uuid4().hex[:4]
        if resolved_user:
            window_name = f"{resolved_user}@{resolved_host}-{short_id}"
        else:
            window_name = f"{resolved_host}-{short_id}"
        
        window_id = window_name
        
        ssh_cmd = "ssh"
        if resolved_port and str(resolved_port) != "22":
            ssh_cmd += f" -p {resolved_port}"
        if resolved_key and resolved_key != "~/.ssh/id_rsa":
             ssh_cmd += f" -i {resolved_key}"
        if resolved_user:
            ssh_cmd += f" {resolved_user}@{resolved_host}"
        else:
            ssh_cmd += f" {resolved_host}"

        new_win = self.session.new_window(window_name=window_id, attach=False, window_shell=ssh_cmd)
        
        # Set a standard large size (120x40)
        try:
            new_win.active_pane.resize_pane(x=120, y=40)
        except:
            pass # Might fail if tmux version doesn't support direct resize on detached pane
            
        new_win.set_option("remain-on-exit", "on")

        for w in self.session.windows:
            if w.window_id != new_win.window_id and w.window_name in ["0", "bash", "fish"]:
                try:
                    w.kill()
                except:
                    pass
        
        return window_id

    def list_windows(self) -> List[Dict[str, str]]:
        """List all active SSH windows."""
        return [
            {"window_id": w.window_name, "active": "unknown"}
            for w in self.session.windows
        ]

    def _strip_ansi(self, text: str) -> str:
        """Strip all ANSI escape sequences."""
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
        text = re.sub(r"\x1b\][^\x07]*\x07", "", text)
        text = re.sub(r"\x1b\][^\x1b]*\x1b\\", "", text)
        text = re.sub(r"\x1b[PX^_][^\x1b]*\x1b\\", "", text)
        text = re.sub(r"<\d+>", "", text)
        text = re.sub(r"[\r\x00\u240c\u23ce]", "", text)
        text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        return text

    def get_snapshot(self, window_id: str, lines: int = 40) -> str:
        """Capture the current screen of the tmux window and clean it."""
        window = self.session.windows.get(window_name=window_id, default=None)
        if not window:
            return f"Error: Window {window_id} not found."
        
        pane = window.active_pane
        # Capture the specified number of lines. 
        # Using '-' for history (e.g. '-100' for last 100 lines including scrollback)
        raw_lines = pane.capture_pane(start=f"-{lines}" if lines > 40 else None)
        
        if len(raw_lines) > lines:
            raw_lines = raw_lines[-lines:]
            
        raw_text = "\n".join(raw_lines)
        return self._strip_ansi(raw_text)

    def send_keys(self, window_id: str, keys: str):
        """Send keys to the tmux window after validation."""
        is_valid, error = self.command_validator.validate_command(keys, check_dangerous=True, pty_aware=True)
        if not is_valid:
            raise ValueError(f"Command validation failed: {error}")

        window = self.session.windows.get(window_name=window_id, default=None)
        if not window:
            raise ValueError(f"Window {window_id} not found")
        
        pane = window.active_pane
        pane.send_keys(keys, enter=True)

    def read_file(self, window_id: str, remote_path: str) -> str:
        """Read a remote file using cat over the tmux session."""
        window = self.session.windows.get(window_name=window_id, default=None)
        if not window:
            raise ValueError(f"Window {window_id} not found")
        
        pane = window.active_pane
        marker = f"__MCP_EOF_{uuid.uuid4().hex[:8]}__"
        cmd = f" cat {remote_path} && echo {marker}"
        
        pane.send_keys(cmd, enter=True)
        
        import time
        max_attempts = 10
        for _ in range(max_attempts):
            time.sleep(0.5)
            # Use raw capture here to avoid line limits
            snapshot = "\n".join(pane.capture_pane(start="-100")) 
            if marker in snapshot:
                parts = snapshot.split(marker)
                if len(parts) >= 3:
                    return self._strip_ansi(parts[1]).strip()
                elif len(parts) == 2:
                    lines = snapshot.splitlines()
                    for i, line in enumerate(lines):
                        if marker in line:
                            if i > 0:
                                return self._strip_ansi("\n".join(lines[:i])).strip()
        
        return ""

    def write_file(self, window_id: str, remote_path: str, content: str, append: bool = False):
        """Write content to a remote file using tee over the tmux session."""
        window = self.session.windows.get(window_name=window_id, default=None)
        if not window:
            raise ValueError(f"Window {window_id} not found")
        
        pane = window.active_pane
        import base64
        encoded_content = base64.b64encode(content.encode()).decode()
        
        redirect = "-a" if append else ""
        cmd = f" echo '{encoded_content}' | base64 -d | tee {redirect} {remote_path} > /dev/null"
        
        pane.send_keys(cmd, enter=True)

    def close_window(self, window_id: str):
        """Close the tmux window and kill session if it's the last one."""
        session = self.session
        window = session.windows.get(window_name=window_id, default=None)
        if window:
            window.kill()
        
        windows = session.windows
        if len(windows) == 0:
            session.kill()
        elif len(windows) == 1 and windows[0].window_name in ["bash", "fish", "0"]:
            session.kill()
