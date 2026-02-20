import pytest
from unittest.mock import MagicMock, patch
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
    mock_instance.sessions.get.assert_called_with(session_name="test-session", default=None)

def test_resolve_connection_success():
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.stdout = "hostname devnull-vm\nuser jon\nport 2222\n"
        manager = TmuxSessionManager()
        config = manager._resolve_connection("devnull-vm")
        
        assert config["hostname"] == "devnull-vm"
        assert config["user"] == "jon"
        assert config["port"] == "2222"

def test_strip_ansi():
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
        mock_session.new_window.return_value = mock_window
        
        window_id = manager.open_ssh("remote-host")
        
        assert "admin@remote-host-" in window_id
        mock_session.new_window.assert_called_once()
        args, kwargs = mock_session.new_window.call_args
        assert "admin@remote-host-" in kwargs["window_name"]

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

def test_read_file_logic(mock_tmux):
    mock_instance, mock_session = mock_tmux
    manager = TmuxSessionManager()
    
    mock_window = MagicMock()
    mock_pane = mock_window.active_pane
    mock_session.windows.get.return_value = mock_window
    
    # Mock snapshot to contain our marker and content
    with patch.object(manager, 'get_snapshot') as mock_snapshot:
        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.hex = "MARKER_LONG_HEX"
            # marker = f"__MCP_EOF_{uuid.uuid4().hex[:8]}__"
            expected_marker = "__MCP_EOF_MARKER_L__"
            
            # Use a more robust side_effect that doesn't StopIteration
            side_effects = [
                f"user@host:~$ cat /tmp/test.txt && echo {expected_marker}",
                f"user@host:~$ cat /tmp/test.txt && echo {expected_marker}\nfile content\n{expected_marker}"
            ]
            
            def side_effect_func(*args, **kwargs):
                if side_effects:
                    return side_effects.pop(0)
                return f"user@host:~$ {expected_marker}"
            
            mock_snapshot.side_effect = side_effect_func
            
            with patch('time.sleep'):
                content = manager.read_file("win-id", "/tmp/test.txt")
                assert content == "file content"
