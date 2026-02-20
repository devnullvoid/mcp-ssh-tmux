import pytest
import time
import os
import subprocess
from mcp_ssh_tmux.session_manager import TmuxSessionManager

# We use localhost for a "real" test if possible.
# This assumes the user has ssh-server running and keys set up.
# We skip if it fails to connect.
def is_localhost_ssh_ready():
    try:
        subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=2", "localhost", "exit"],
            check=True, capture_output=True
        )
        return True
    except:
        return False

@pytest.fixture(autouse=True)
def cleanup_test_session():
    """Cleanup the test tmux session after each test."""
    yield
    import libtmux
    server = libtmux.Server()
    session = server.sessions.get(session_name="mcp-ssh-test", default=None)
    if session:
        session.kill()

@pytest.mark.skipif(not is_localhost_ssh_ready(), reason="Localhost SSH not accessible")
def test_live_localhost_session():
    manager = TmuxSessionManager(session_name="mcp-ssh-test")
    window_id = None
    try:
        # 1. Open Session
        window_id = manager.open_ssh("localhost")
        assert window_id is not None
        
        # 2. Wait for login and capture snapshot
        time.sleep(2) # Give it time to connect
        snapshot = manager.get_snapshot(window_id)
        assert len(snapshot) > 0
        print(f"\nInitial snapshot length: {len(snapshot)}")
        
        # 3. Run a simple command
        manager.send_keys(window_id, "echo 'hello world'")
        time.sleep(1)
        snapshot = manager.get_snapshot(window_id)
        assert "hello world" in snapshot
        
        # 4. Test read_file
        test_file = f"/tmp/mcp_test_{int(time.time())}.txt"
        with open(test_file, "w") as f:
            f.write("secret data")
        
        try:
            content = manager.read_file(window_id, test_file)
            assert "secret data" in content
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

        # 5. Test write_file
        remote_write_path = f"/tmp/mcp_write_test_{int(time.time())}.txt"
        manager.write_file(window_id, remote_write_path, "written from mcp")
        time.sleep(1)
        
        # Verify write
        with open(remote_write_path, "r") as f:
            content = f.read().strip()
            assert content == "written from mcp"
        
        if os.path.exists(remote_write_path):
            os.remove(remote_write_path)
    finally:
        # 6. Cleanup
        if window_id:
            manager.close_window(window_id)

def test_resolve_connection_live():
    # Test that ssh -G actually works for a known alias or localhost
    manager = TmuxSessionManager(session_name="mcp-ssh-test")
    config = manager._resolve_connection("localhost")
    assert "hostname" in config
    assert config["hostname"] == "localhost"
