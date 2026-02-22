import re
from typing import Optional
from fastmcp import FastMCP
from .session_manager import TmuxSessionManager

mcp = FastMCP("ssh-tmux")
_session_manager: Optional[TmuxSessionManager] = None

def get_manager() -> TmuxSessionManager:
    """Lazy-initialize the session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = TmuxSessionManager()
    return _session_manager

def get_snapshot_with_hints(session_id: str, lines: int = 40) -> str:
    """Capture snapshot and append helpful hints about the session state."""
    snapshot = get_manager().get_snapshot(session_id, lines=lines)
    
    # Analyze the last few characters for a shell prompt
    # Common prompts: $, #, >, %
    last_line = snapshot.splitlines()[-1] if snapshot.strip() else ""
    
    hint = ""
    if re.search(r"[$#>%]\s*$", last_line):
        hint = "\n\n[INFO: A shell prompt was detected at the end of the screen. The command has likely finished.]"
    elif re.search(r"\[[Yy]/[Nn]\]|password:|passphrase:", last_line, re.IGNORECASE):
        hint = "\n\n[INFO: The session appears to be waiting for interactive input (e.g., a password or confirmation).]"
    
    return snapshot + hint

@mcp.tool()
def open_session(host: str, username: Optional[str] = None, port: Optional[int] = None) -> str:
    """Open a new SSH session in a tmux window. Returns the session_id."""
    window_id = get_manager().open_ssh(host, username, port)
    return f"Session opened. ID: {window_id}\n\nInitial Snapshot:\n{get_snapshot_with_hints(window_id)}"

@mcp.tool()
def send_command(session_id: str, command: str, lines: int = 40) -> str:
    """Send a command to an active session and return the screen snapshot.
    
    Args:
        session_id: The ID of the session.
        command: The command to send.
        lines: Number of lines to capture from the end of the screen (default 40).
    """
    try:
        get_manager().send_keys(session_id, command)
        
        # Poll for a few seconds to see if a prompt appears or output settles
        import time
        max_poll = 2.0
        start_time = time.time()
        snapshot = ""
        while time.time() - start_time < max_poll:
            time.sleep(0.2)
            snapshot = get_snapshot_with_hints(session_id, lines=lines)
            # If we see a prompt info hint, the command likely finished
            if "[INFO: A shell prompt was detected" in snapshot:
                break
            # If we see an interactive prompt hint, return immediately
            if "[INFO: The session appears to be waiting for interactive input" in snapshot:
                break
                
        return snapshot
    except ValueError as e:
        return str(e)

@mcp.tool()
def get_snapshot(session_id: str, lines: int = 40) -> str:
    """Get the current screen state of a session.
    
    Args:
        session_id: The ID of the session.
        lines: Number of lines to capture from the end of the screen (default 40).
    """
    return get_snapshot_with_hints(session_id, lines=lines)

@mcp.tool()
def list_sessions() -> str:
    """List all active SSH sessions."""
    sessions = get_manager().list_windows()
    if not sessions:
        return "No active sessions."
    return "\n".join([f"- {s['window_id']}" for s in sessions])

@mcp.tool()
def close_session(session_id: str) -> str:
    """Close an active SSH session and return its final screen state."""
    snapshot = get_snapshot_with_hints(session_id)
    get_manager().close_window(session_id)
    return f"Session {session_id} closed.\n\nFinal Snapshot:\n{snapshot}"

@mcp.resource("ssh-tmux://{session_id}/snapshot")
def get_session_snapshot_resource(session_id: str) -> str:
    """Live snapshot of the terminal screen."""
    return get_snapshot_with_hints(session_id)

@mcp.tool()
def read_remote_file(session_id: str, remote_path: str) -> str:
    """Read a file from the remote host using the established session."""
    try:
        content = get_manager().read_file(session_id, remote_path)
        return content if content else f"No content found for {remote_path} or file read timed out."
    except Exception as e:
        return f"Error reading remote file: {str(e)}"

@mcp.tool()
def write_remote_file(session_id: str, remote_path: str, content: str, append: bool = False) -> str:
    """Write content to a file on the remote host using the established session."""
    try:
        get_manager().write_file(session_id, remote_path, content, append)
        return f"Successfully wrote to {remote_path}"
    except Exception as e:
        return f"Error writing remote file: {str(e)}"

if __name__ == "__main__":
    mcp.run()
