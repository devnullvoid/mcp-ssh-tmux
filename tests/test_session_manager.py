import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from mcp_ssh_tmux.session_manager import TmuxSessionManager

@pytest.fixture
def mock_tmux():
    with patch('libtmux.Server') as mock_server:
        mock_instance = mock_server.return_value
        mock_session = MagicMock()
        # Mock server.sessions.get
        mock_instance.sessions.get.return_value = mock_session
        yield mock_instance, mock_session

def test_session_manager_init(mock_tmux):
    mock_instance, mock_session = mock_tmux
    manager = TmuxSessionManager(session_name="test-session")
    
    assert manager.session_name == "test-session"
    # Access the session property to trigger the call
    _ = manager.session
    mock_instance.sessions.get.assert_called_with(session_name="test-session", default=None)

def test_resolve_connection_success(mock_tmux):
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.stdout = "hostname devnull-vm\nuser jon\nport 2222\n"
        manager = TmuxSessionManager()
        config = manager._resolve_connection("devnull-vm")
        
        assert config["hostname"] == "devnull-vm"
        assert config["user"] == "jon"
        assert config["port"] == "2222"

def test_strip_ansi(mock_tmux):
    manager = TmuxSessionManager()
    text_with_ansi = "\x1b[31mError\x1b[0m: \x1b[1mBold\x1b[0m"
    clean_text = manager._strip_ansi(text_with_ansi)
    assert clean_text == "Error: Bold"

def test_open_ssh_naming(mock_tmux):
    mock_instance, mock_session = mock_tmux
    manager = TmuxSessionManager()
    
    with patch.object(manager, '_resolve_connection') as mock_resolve:
        mock_resolve.return_value = {"hostname": "remote-host", "user": "admin"}
        
        mock_window = MagicMock()
        mock_window.window_name = "admin@remote-host-xxxx"
        mock_window.window_id = "@123"
        mock_session.new_window.return_value = mock_window
        mock_session.windows = [mock_window]
        
        window_id = manager.open_ssh("remote-host")
        
        assert "admin@remote-host-" in window_id
        mock_session.new_window.assert_called_once()

def test_list_multiple_windows(mock_tmux):
    mock_instance, mock_session = mock_tmux
    manager = TmuxSessionManager()
    
    # Mock multiple windows
    win1 = MagicMock()
    win1.window_name = "user@host1-aaaa"
    win2 = MagicMock()
    win2.window_name = "user@host1-bbbb" # Same host, different ID
    win3 = MagicMock()
    win3.window_name = "admin@host2-cccc" # Different host
    
    mock_session.windows = [win1, win2, win3]
    
    sessions = manager.list_windows()
    assert len(sessions) == 3
    ids = [s["window_id"] for s in sessions]
    assert "user@host1-aaaa" in ids
    assert "user@host1-bbbb" in ids
    assert "admin@host2-cccc" in ids

@pytest.mark.asyncio
async def test_read_file_logic(mock_tmux):
    mock_instance, mock_session = mock_tmux
    manager = TmuxSessionManager()
    
    mock_window = MagicMock()
    mock_pane = mock_window.active_pane
    mock_session.windows.get.return_value = mock_window
    
    # In read_file, we use pane.capture_pane() directly
    # and we call get_snapshot which also calls capture_pane
    
    with patch.object(manager, 'get_snapshot') as mock_snapshot:
        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.hex = "MARKER_LONG_HEX"
            expected_marker = "__MCP_EOF_MARKER_L__"
            
            # Setup mock for pane.capture_pane used in read_file
            mock_pane.capture_pane.return_value = [
                f"user@host:~$ cat /tmp/test.txt && echo {expected_marker}",
                "file content",
                f"{expected_marker}"
            ]
            
            # Setup mock_snapshot for any other calls
            mock_snapshot.return_value = f"file content\n{expected_marker}"
            
            with patch('asyncio.sleep', new_callable=AsyncMock):
                content = await manager.read_file("win-id", "/tmp/test.txt")
                assert content == "file content"

@pytest.mark.asyncio
async def test_read_file_prefers_direct_ssh(mock_tmux):
    mock_instance, mock_session = mock_tmux
    manager = TmuxSessionManager()
    manager._window_connections["win-id"] = {
        "host": "remote-host",
        "user": "admin",
        "port": "2222",
        "identityfile": "~/.ssh/id_ed25519",
    }

    mock_window = MagicMock()
    mock_session.windows.get.return_value = mock_window

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = b"full file contents\n"

        content = await manager.read_file("win-id", "/tmp/test.txt")

        assert content == "full file contents\n"
        mock_window.active_pane.send_keys.assert_not_called()
        mock_run.assert_called_once()
        ssh_cmd = mock_run.call_args.args[0]
        assert ssh_cmd[:5] == ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5"]
        assert "-p" in ssh_cmd
        assert "admin@remote-host" in ssh_cmd
        assert ssh_cmd[-1] == "cat -- /tmp/test.txt"

@pytest.mark.asyncio
async def test_read_file_falls_back_to_pane_capture(mock_tmux):
    mock_instance, mock_session = mock_tmux
    manager = TmuxSessionManager()

    mock_window = MagicMock()
    mock_pane = mock_window.active_pane
    mock_session.windows.get.return_value = mock_window

    with patch.object(manager, "_read_file_via_direct_ssh", return_value=None):
        with patch("uuid.uuid4") as mock_uuid:
            mock_uuid.return_value.hex = "MARKER_LONG_HEX"
            expected_marker = "__MCP_EOF_MARKER_L__"
            mock_pane.capture_pane.return_value = [
                f"user@host:~$ cat -- /tmp/test.txt && echo {expected_marker}",
                "file content",
                expected_marker,
            ]

            with patch("asyncio.sleep", new_callable=AsyncMock):
                content = await manager.read_file("win-id", "/tmp/test.txt")

            assert content == "file content"
            mock_pane.capture_pane.assert_called_with(
                start=f"-{manager.READ_FILE_FALLBACK_HISTORY_LINES}"
            )

@pytest.mark.asyncio
async def test_read_file_uses_custom_fallback_lines(mock_tmux):
    mock_instance, mock_session = mock_tmux
    manager = TmuxSessionManager()

    mock_window = MagicMock()
    mock_pane = mock_window.active_pane
    mock_session.windows.get.return_value = mock_window

    with patch.object(manager, "_read_file_via_direct_ssh", return_value=None):
        with patch("uuid.uuid4") as mock_uuid:
            mock_uuid.return_value.hex = "MARKER_LONG_HEX"
            expected_marker = "__MCP_EOF_MARKER_L__"
            mock_pane.capture_pane.return_value = [
                f"user@host:~$ cat -- /tmp/test.txt && echo {expected_marker}",
                "file content",
                expected_marker,
            ]

            with patch("asyncio.sleep", new_callable=AsyncMock):
                content = await manager.read_file(
                    "win-id",
                    "/tmp/test.txt",
                    fallback_lines=500,
                )

            assert content == "file content"
            mock_pane.capture_pane.assert_called_with(start="-500")
