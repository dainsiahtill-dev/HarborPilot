import os
import sys
import shutil
import tempfile
import pytest

# Add backend directory to sys.path so we can import app modules
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

@pytest.fixture
def mock_workspace():
    """Create a temporary workspace directory for testing file operations."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)
