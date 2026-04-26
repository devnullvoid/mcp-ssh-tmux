import os
import libtmux
import uuid
import subprocess
import re
import shlex
from typing import Optional, List, Dict, Any
from pathlib import Path
from .validation import CommandValidator

class TmuxSessionManager:
    READ_FILE_FALLBACK_HISTORY_LINES = 200

    def __init__(self, session_name: str = "mcp-ssh"):
        self.session_name = session_name
        self.server = libtmux.Server()
        self._session = None
        self._window_connections: Dict[str, Dict[str, Optional[str]]] = {}
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
        self._window_connections[window_id] = {
            "host": resolved_host,
            "user": resolved_user,
            "port": str(resolved_port) if resolved_port else None,
            "identityfile": resolved_key,
        }
        
        # Set a standard large size (120x40)
        try:
            new_win.active_pane.resize_pane(x=120, y=40)
        except:
            pass # Might fail if tmux version doesn't support direct resize on detached pane
            
        new_win.set_option("remain-on-exit", "on")

        # Cleanup ANY other windows if this is our first SSH window
        # (Usually just the one default window created by libtmux)
        all_windows = self.session.windows
        if len(all_windows) > 1:
            for w in all_windows:
                if w.window_id != new_win.window_id:
                    # If the other window is a default one (no '@' or '-' usually)
                    # or if it's named 0, bash, fish, zsh
                    if "@" not in w.window_name or w.window_name in ["0", "bash", "fish", "zsh"]:
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

    def _get_connection_info(self, window_id: str) -> Dict[str, Optional[str]]:
        """Return the resolved SSH connection info for a window."""
        connection = self._window_connections.get(window_id)
        if connection:
            return connection

        window = self.session.windows.get(window_name=window_id, default=None)
        if not window:
            raise ValueError(f"Window {window_id} not found")

        # Best-effort fallback for sessions restored from an existing tmux server.
        window_name = window.window_name
        host_part = window_name.rsplit("-", 1)[0]
        if "@" in host_part:
            user, host = host_part.split("@", 1)
        else:
            user, host = None, host_part

        connection = {
            "host": host,
            "user": user,
            "port": None,
            "identityfile": None,
        }
        self._window_connections[window_id] = connection
        return connection

    def _build_ssh_command(self, window_id: str) -> List[str]:
        """Build a direct SSH command for out-of-band file transfer attempts."""
        connection = self._get_connection_info(window_id)
        host = connection.get("host")
        if not host:
            raise ValueError(f"Missing host info for window {window_id}")

        cmd = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
        ]
        port = connection.get("port")
        if port and port != "22":
            cmd.extend(["-p", port])

        identityfile = connection.get("identityfile")
        if identityfile and identityfile != "~/.ssh/id_rsa":
            cmd.extend(["-i", identityfile])

        user = connection.get("user")
        cmd.append(f"{user}@{host}" if user else host)
        return cmd

    def _read_file_via_direct_ssh(self, window_id: str, remote_path: str) -> Optional[str]:
        """Try to read the remote file via a fresh SSH exec instead of pane capture."""
        cmd = self._build_ssh_command(window_id)
        cmd.append(f"cat -- {shlex.quote(remote_path)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout.decode("utf-8", errors="replace")

    def send_keys(self, window_id: str, keys: str, literal: bool = False):
        """Send keys to the tmux window after validation.
        
        Args:
            window_id: The window identifier
            keys: Keys to send (can include tmux key notation like C-c, C-d)
            literal: If True, send keys without Enter and skip command validation
        """
        if not literal:
            is_valid, error = self.command_validator.validate_command(keys, check_dangerous=True, pty_aware=True)
            if not is_valid:
                raise ValueError(f"Command validation failed: {error}")

        window = self.session.windows.get(window_name=window_id, default=None)
        if not window:
            raise ValueError(f"Window {window_id} not found")
        
        pane = window.active_pane
        if literal:
            # Split into separate args so tmux interprets key names
            # e.g. "yes Enter" → tmux send-keys yes Enter
            pane.cmd("send-keys", *keys.split())
        else:
            pane.send_keys(keys, enter=True, literal=False)

    async def read_file(
        self,
        window_id: str,
        remote_path: str,
        fallback_lines: Optional[int] = None,
    ) -> str:
        """Read a remote text file, preferring a direct SSH exec over pane capture."""
        window = self.session.windows.get(window_name=window_id, default=None)
        if not window:
            raise ValueError(f"Window {window_id} not found")

        direct_content = self._read_file_via_direct_ssh(window_id, remote_path)
        if direct_content is not None:
            return direct_content

        pane = window.active_pane
        marker = f"__MCP_EOF_{uuid.uuid4().hex[:8]}__"
        quoted_path = shlex.quote(remote_path)
        cmd = f" cat -- {quoted_path} && echo {marker}"
        history_lines = fallback_lines or self.READ_FILE_FALLBACK_HISTORY_LINES
        
        pane.send_keys(cmd, enter=True)
        
        import asyncio
        max_attempts = 10
        for attempt in range(max_attempts):
            await asyncio.sleep(0.5)
            # Keep PTY fallback bounded so long-lived sessions do not dump massive scrollback.
            snapshot = "\n".join(
                pane.capture_pane(start=f"-{history_lines}")
            )
            
            if marker in snapshot:
                # Find the command line and marker line
                lines = snapshot.splitlines()
                cmd_idx = None
                marker_idx = None
                
                for i, line in enumerate(lines):
                    if cmd.strip() in line or f"cat {remote_path}" in line:
                        cmd_idx = i
                    if marker in line:
                        marker_idx = i
                
                # Extract content between command and marker
                if cmd_idx is not None and marker_idx is not None and marker_idx > cmd_idx:
                    content_lines = lines[cmd_idx + 1:marker_idx]
                    return self._strip_ansi("\n".join(content_lines)).strip()
        
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
        try:
            session = self.session
            window = session.windows.get(window_name=window_id, default=None)
            if window:
                window.kill()
            self._window_connections.pop(window_id, None)
            
            # Check if any non-default windows remain
            try:
                remaining = session.windows
                if len(remaining) == 0:
                    session.kill()
                elif len(remaining) == 1 and remaining[0].window_name in ["0", "bash", "fish", "zsh"]:
                    session.kill()
            except:
                pass # Session already gone
        except:
            pass # Server/Session inaccessible
