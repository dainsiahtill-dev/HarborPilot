"""
pytest configuration and fixtures for HarborPilot E2E tests
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Generator, Optional
import pytest
import json
from unittest.mock import Mock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from playwright.sync_api import Page, BrowserContext, Browser
from loguru import logger


# ================================
# Global Configuration
# ================================

def pytest_configure(config):
    """Configure pytest with custom markers and settings"""
    config.addinivalue_line(
        "markers", "smoke: mark test as smoke test"
    )
    config.addinivalue_line(
        "markers", "regression: mark test as regression test"
    )
    config.addinivalue_line(
        "markers", "dashboard: mark test as Dashboard functionality test"
    )
    config.addinivalue_line(
        "markers", "workflow: mark test as complete workflow test"
    )
    config.addinivalue_line(
        "markers", "mock_ai: mark test as using mocked AI responses"
    )


# ================================
# Environment Fixtures
# ================================

@pytest.fixture(scope="session")
def test_config() -> Dict[str, Any]:
    """Load test configuration"""
    config = {
        "base_url": os.getenv("HARBORPILOT_TEST_BASE_URL", "http://localhost:5173"),
        "workspace_root": os.getenv("HARBORPILOT_TEST_WORKSPACE_ROOT", "/tmp/harborpilot-test"),
        "mock_ai": os.getenv("HARBORPILOT_MOCK_AI", "true").lower() == "true",
        "mock_responses_path": os.getenv("HARBORPILOT_MOCK_RESPONSES_PATH", "./fixtures/responses"),
        "timeout": int(os.getenv("HARBORPILOT_TEST_TIMEOUT", "30000")),
        "retries": int(os.getenv("HARBORPILOT_TEST_RETRIES", "3")),
    }
    
    # Create directories if they don't exist
    Path(config["workspace_root"]).mkdir(parents=True, exist_ok=True)
    Path(config["mock_responses_path"]).mkdir(parents=True, exist_ok=True)
    
    return config


@pytest.fixture(scope="session")
def temp_workspace_root(test_config) -> Generator[Path, None, None]:
    """Create temporary workspace root for testing"""
    temp_root = Path(tempfile.mkdtemp(prefix="harborpilot_e2e_"))
    
    yield temp_root
    
    # Cleanup
    if temp_root.exists():
        shutil.rmtree(temp_root)


# ================================
# Browser Fixtures
# ================================

@pytest.fixture(scope="function")
def page(page: Page, test_config) -> Page:
    """Configure page with test settings"""
    # Set default timeout
    page.set_default_timeout(test_config["timeout"])
    
    # Add error handling
    page.on("pageerror", lambda error: logger.error(f"Page error: {error}"))
    page.on("requestfailed", lambda request: logger.error(f"Request failed: {request.url}"))
    
    return page


@pytest.fixture(scope="function")
def authenticated_page(page: Page, test_config) -> Page:
    """Create authenticated page for tests that require login"""
    # Navigate to login page
    page.goto(f"{test_config['base_url']}/login")
    
    # Mock authentication (adjust based on actual auth flow)
    page.evaluate("""
        () => {
            localStorage.setItem('auth_token', 'test_token');
            localStorage.setItem('user', JSON.stringify({id: 'test_user', name: 'Test User'}));
        }
    """)
    
    return page


# ================================
# Workspace Fixtures
# ================================

@pytest.fixture(scope="function")
def sample_workspace(temp_workspace_root) -> Generator[Dict[str, Any], None, None]:
    """Create a sample workspace for testing"""
    workspace_name = "test_project"
    workspace_path = temp_workspace_root / workspace_name
    
    # Create workspace structure
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    # Create basic project structure
    (workspace_path / "docs").mkdir(exist_ok=True)
    (workspace_path / "src").mkdir(exist_ok=True)
    (workspace_path / "tests").mkdir(exist_ok=True)
    
    # Create requirements document
    requirements_content = """
# Test Project Requirements

## Overview
This is a test project for HarborPilot E2E testing.

## Features
1. User authentication
2. Data visualization
3. Report generation

## Technical Requirements
- Python 3.10+
- React frontend
- REST API backend
"""
    
    (workspace_path / "docs" / "requirements.md").write_text(requirements_content.strip())
    
    # Create basic Python file
    py_content = '''
def hello_world():
    """Simple hello world function"""
    return "Hello, HarborPilot!"

if __name__ == "__main__":
    print(hello_world())
'''
    
    (workspace_path / "src" / "main.py").write_text(py_content.strip())
    
    # Create package.json for frontend
    package_json = {
        "name": "test-project",
        "version": "1.0.0",
        "scripts": {
            "dev": "vite",
            "build": "vite build",
            "test": "pytest"
        }
    }
    
    (workspace_path / "package.json").write_text(json.dumps(package_json, indent=2))
    
    workspace_info = {
        "name": workspace_name,
        "path": str(workspace_path),
        "type": "python",
        "has_docs": True,
        "has_requirements": True,
    }
    
    yield workspace_info
    
    # Cleanup
    if workspace_path.exists():
        shutil.rmtree(workspace_path)


@pytest.fixture(scope="function")
def empty_workspace(temp_workspace_root) -> Generator[Dict[str, Any], None, None]:
    """Create an empty workspace for testing"""
    workspace_name = "empty_project"
    workspace_path = temp_workspace_root / workspace_name
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    workspace_info = {
        "name": workspace_name,
        "path": str(workspace_path),
        "type": "empty",
        "has_docs": False,
        "has_requirements": False,
    }
    
    yield workspace_info
    
    # Cleanup
    if workspace_path.exists():
        shutil.rmtree(workspace_path)


# ================================
# AI Mocking Fixtures
# ================================

@pytest.fixture(scope="function")
def mock_ai_responses(test_config):
    """Load mock AI responses for testing"""
    responses_path = Path(test_config["mock_responses_path"])
    
    # Default mock responses
    default_responses = {
        "pm_response": {
            "status": "success",
            "tasks": [
                {
                    "id": "task_1",
                    "title": "Set up project structure",
                    "goal": "Create basic project structure with documentation",
                    "acceptance": ["Project structure created", "Documentation in place"]
                }
            ]
        },
        "director_response": {
            "status": "success",
            "changes": ["Created main.py", "Added documentation"],
            "qa_passed": True
        }
    }
    
    # Load from files if available
    responses = {}
    for response_type, default_content in default_responses.items():
        response_file = responses_path / f"{response_type}.json"
        if response_file.exists():
            with open(response_file, 'r') as f:
                responses[response_type] = json.load(f)
        else:
            responses[response_type] = default_content
    
    return responses


@pytest.fixture(scope="function")
def mock_codex_service(mock_ai_responses):
    """Mock Codex service for testing"""
    with patch('modules.harborpilot-loop.codex_utils.call_codex') as mock:
        mock.return_value = mock_ai_responses["pm_response"]
        yield mock


@pytest.fixture(scope="function")
def mock_ollama_service(mock_ai_responses):
    """Mock Ollama service for testing"""
    with patch('modules.harborpilot-loop.ollama_utils.invoke_ollama') as mock:
        mock.return_value = mock_ai_responses["director_response"]
        yield mock


# ================================
# State Management Fixtures
# ================================

@pytest.fixture(scope="function")
def mock_state_files(temp_workspace_root):
    """Create mock state files for testing"""
    state_dir = temp_workspace_root / "state" / "ollama"
    state_dir.mkdir(parents=True, exist_ok=True)
    
    # Mock PM_TASKS.json
    pm_tasks = {
        "schema_version": 1,
        "run_id": "test_run_123",
        "pm_iteration": 1,
        "tasks": [
            {
                "id": "task_1",
                "title": "Test Task",
                "goal": "Test goal",
                "acceptance": ["Test acceptance"]
            }
        ]
    }
    
    (state_dir / "PM_TASKS.json").write_text(json.dumps(pm_tasks, indent=2))
    
    # Mock DIRECTOR_RESULT.json
    director_result = {
        "schema_version": 1,
        "status": "success",
        "run_id": "test_run_123",
        "patch_risk": {"score": 0, "factors": {}}
    }
    
    (state_dir / "DIRECTOR_RESULT.json").write_text(json.dumps(director_result, indent=2))
    
    # Mock DIALOGUE.jsonl
    dialogue_lines = [
        json.dumps({
            "timestamp": "2024-01-01T00:00:00Z",
            "speaker": "PM",
            "type": "handoff",
            "content": "Starting test workflow"
        })
    ]
    
    (state_dir / "DIALOGUE.jsonl").write_text("\n".join(dialogue_lines))
    
    return state_dir


# ================================
# Utility Fixtures
# ================================

@pytest.fixture(scope="function")
def test_logger():
    """Create logger for test functions"""
    return logger


@pytest.fixture(scope="function")
def screenshot_on_failure(page: Page, request):
    """Take screenshot on test failure"""
    yield
    
    if request.node.rep_call.failed:
        # Create screenshots directory if it doesn't exist
        screenshots_dir = Path("reports/screenshots")
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # Take screenshot
        screenshot_name = f"{request.node.name}_{int(time.time())}.png"
        screenshot_path = screenshots_dir / screenshot_name
        page.screenshot(path=str(screenshot_path), full_page=True)
        logger.info(f"Screenshot saved: {screenshot_path}")


# ================================
# Hooks
# ================================

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Make test result information available to fixtures"""
    outcome = yield
    rep = outcome.get_result()
    
    setattr(item, "rep_" + rep.when, rep)


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup global test environment"""
    # Set environment variables for testing
    os.environ["HARBORPILOT_ENV"] = "test"
    os.environ["HARBORPILOT_LOG_LEVEL"] = "DEBUG"
    
    # Create necessary directories
    Path("reports").mkdir(exist_ok=True)
    Path("reports/screenshots").mkdir(exist_ok=True)
    Path("test-results").mkdir(exist_ok=True)
    
    yield
    
    # Cleanup if needed
    pass
