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
        self.session = self._ensure_session()
        self.command_validator = CommandValidator()

    def _ensure_session(self):
        """Ensure the dedicated tmux session exists."""
        session = self.server.sessions.get(session_name=self.session_name, default=None)
        if not session:
            session = self.server.new_session(session_name=self.session_name)
        return session

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
            # Fallback if ssh -G fails (e.g. host not in config and not a valid hostname)
            return {"hostname": host}

    def open_ssh(self, host: str, username: Optional[str] = None, port: Optional[int] = None) -> str:
        """Open a new SSH connection in a new tmux window."""
        config = self._resolve_connection(host)
        
        resolved_host = config.get("hostname", host)
        resolved_user = username or config.get("user")
        resolved_port = port or config.get("port")
        resolved_key = config.get("identityfile")

        # Create window name with host/user info
        short_id = uuid.uuid4().hex[:4]
        if resolved_user:
            window_name = f"{resolved_user}@{resolved_host}-{short_id}"
        else:
            window_name = f"{resolved_host}-{short_id}"
        
        window_id = window_name
        
        # Build the SSH command
        ssh_cmd = "ssh"
        if resolved_port and str(resolved_port) != "22":
            ssh_cmd += f" -p {resolved_port}"
        if resolved_key and resolved_key != "~/.ssh/id_rsa": # Only add if not default or exists
             # ssh -G usually returns the absolute path
             ssh_cmd += f" -i {resolved_key}"
        if resolved_user:
            ssh_cmd += f" {resolved_user}@{resolved_host}"
        else:
            ssh_cmd += f" {resolved_host}"

        # Create window and run command DIRECTLY
        window = self.session.new_window(window_name=window_id, attach=False, window_shell=ssh_cmd)
        
        # Set remain-on-exit so we can see why a session died
        window.set_option("remain-on-exit", "on")

        # Cleanup the default initial window if it's still there and empty
        # This ensures the session will actually close when all SSH windows are gone
        for w in self.session.windows:
            if w.window_name in ["0", "bash"] and w.window_id != window.window_id:
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
        """Strip all ANSI escape sequences including CSI, OSC, and other types."""
        # Remove CSI sequences: \x1b[...
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
        # Remove OSC sequences: \x1b]...(\x07|\x1b\\)
        text = re.sub(r"\x1b\][^\x07]*\x07", "", text)
        text = re.sub(r"\x1b\][^\x1b]*\x1b\\", "", text)
        # Remove other escape sequences
        text = re.sub(r"\x1b[PX^_][^\x1b]*\x1b\\", "", text)
        # Remove terminal UI noise like <N> (fish iTerm integration)
        text = re.sub(r"<\d+>", "", text)
        # Remove special characters that appear in terminal output
        text = re.sub(r"[\r\x00\u240c\u23ce]", "", text)
        # Remove any remaining single control characters
        text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        return text

    def get_snapshot(self, window_id: str) -> str:
        """Capture the current screen of the tmux window and clean it."""
        window = self.session.windows.get(window_name=window_id, default=None)
        if not window:
            return f"Error: Window {window_id} not found."
        
        pane = window.active_pane
        raw_text = "\n".join(pane.capture_pane())
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
        # Use a unique marker to capture only the file content
        marker = f"__MCP_EOF_{uuid.uuid4().hex[:8]}__"
        # Prefix with a space to avoid shell history (if HISTCONTROL=ignorespace is set)
        cmd = f" cat {remote_path} && echo {marker}"
        
        pane.send_keys(cmd, enter=True)
        
        # Wait and capture
        import time
        max_attempts = 10
        for _ in range(max_attempts):
            time.sleep(0.5)
            snapshot = self.get_snapshot(window_id)
            if marker in snapshot:
                # Find the marker that was part of our command
                # Pattern: user@host:~$ cat file && echo EOF_MARKER
                # Then: file content
                # Then: EOF_MARKER
                
                # Split by marker - we expect at least 3 parts if both are present
                # 1. Before command (empty or prompt)
                # 2. Between echo marker and second marker (the content)
                # 3. After second marker (empty or prompt)
                
                parts = snapshot.split(marker)
                if len(parts) >= 3:
                    # parts[0] is everything before first marker (prompt + cat cmd)
                    # parts[1] is everything between first and second marker (the content)
                    # We might have some trailing characters from the first line (newline after echo marker)
                    content = parts[1].strip()
                    return content
                elif len(parts) == 2:
                    # Maybe only one marker is visible? Let's be cautious.
                    # If marker is at the end, the content is between the command and the marker.
                    lines = snapshot.splitlines()
                    for i, line in enumerate(lines):
                        if marker in line:
                            # If it's the second occurrence (not the echo command)
                            if i > 0 and marker not in lines[0]:
                                return "\n".join(lines[:i]).strip()
        
        return ""

    def write_file(self, window_id: str, remote_path: str, content: str, append: bool = False):
        """Write content to a remote file using tee over the tmux session."""
        window = self.session.windows.get(window_name=window_id, default=None)
        if not window:
            raise ValueError(f"Window {window_id} not found")
        
        pane = window.active_pane
        
        # Use base64 to avoid shell escaping issues
        import base64
        encoded_content = base64.b64encode(content.encode()).decode()
        
        redirect = "-a" if append else ""
        # Prefix with a space to avoid shell history
        cmd = f" echo '{encoded_content}' | base64 -d | tee {redirect} {remote_path} > /dev/null"
        
        pane.send_keys(cmd, enter=True)

    def close_window(self, window_id: str):
        """Close the tmux window and kill session if it's the last one."""
        window = self.session.windows.get(window_name=window_id, default=None)
        if window:
            window.kill()
        
        # If no windows are left (or only the automatic 'bash/fish' window that sometimes spawns)
        # we kill the session to be sure.
        if len(self.session.windows) == 0:
            self.session.kill()
        elif len(self.session.windows) == 1 and self.session.windows[0].window_name in ["bash", "fish", "0"]:
            self.session.kill()
