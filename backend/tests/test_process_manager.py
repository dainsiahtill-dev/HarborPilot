import subprocess
from unittest import mock
from app.state import ProcessHandle, AppState, Settings

def test_process_handle_defaults():
    handle = ProcessHandle()
    assert handle.process is None
    assert handle.mode == ""

def test_app_state_initialization():
    settings = Settings(workspace="/tmp")
    state = AppState(settings=settings)
    assert state.settings.workspace == "/tmp"
    assert isinstance(state.pm, ProcessHandle)
    assert isinstance(state.director, ProcessHandle)

def test_mock_subprocess_lifecycle():
    with mock.patch("subprocess.Popen") as mock_popen:
        mock_process = mock.Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        handle = ProcessHandle()
        handle.process = subprocess.Popen(["ls"], stdout=subprocess.PIPE)
        handle.started_at = 1000.0
        
        assert handle.process.pid == 12345
        assert handle.process.poll() is None
        
        # Simulate termination
        handle.process.terminate()
        mock_process.terminate.assert_called_once()
