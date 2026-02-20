import pytest
from mcp_ssh_tmux.validation import CommandValidator, OutputLimiter

def test_validate_safe_command():
    is_valid, error = CommandValidator.validate_command("ls -la")
    assert is_valid
    assert error is None

def test_validate_dangerous_command():
    # Dangerous commands should be blocked when check_dangerous=True
    is_valid, error = CommandValidator.validate_command("rm -rf /", check_dangerous=True)
    assert not is_valid
    assert "Dangerous command blocked" in error

def test_validate_background_command():
    # Background commands should be blocked
    is_valid, error = CommandValidator.validate_command("sleep 100 &")
    assert not is_valid
    assert "Background process blocked" in error

def test_validate_tmux_invocation():
    # Direct tmux invocation should be blocked
    is_valid, error = CommandValidator.validate_command("tmux new-session")
    assert not is_valid
    assert "tmux invocation blocked" in error

def test_validate_screen_invocation():
    # Direct screen invocation should be blocked
    is_valid, error = CommandValidator.validate_command("screen")
    assert not is_valid
    assert "screen invocation blocked" in error

def test_output_limiter():
    limiter = OutputLimiter(max_size=10)
    
    # Within limit
    chunk, should_continue = limiter.add_chunk("abcde")
    assert chunk == "abcde"
    assert should_continue
    
    # Exceeding limit
    chunk, should_continue = limiter.add_chunk("fghijklmnopqrst")
    assert "OUTPUT TRUNCATED" in chunk
    assert not should_continue
    assert limiter.truncated

def test_pty_aware_tmux_validation():
    # In PTY-aware mode, some tmux discovery commands might be allowed 
    # (though our current implementation is strict if strict=True)
    is_valid, error = CommandValidator.validate_command("tmux list-sessions", pty_aware=True)
    # Our current implementation in _is_blocked_tmux_usage:
    # if strict: return True
    # if not args: return True (for bare tmux)
    # So "tmux list-sessions" with pty_aware=True should be ALLOWED because:
    # subcommand is "list-sessions", which is NOT in {"attach", "new", etc.}
    assert is_valid
    assert error is None

    # But "tmux attach" should still be blocked
    is_valid, error = CommandValidator.validate_command("tmux attach", pty_aware=True)
    assert not is_valid
    assert "tmux invocation blocked" in error
