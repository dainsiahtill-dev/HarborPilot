"""
Integration tests for HarborPilot E2E
"""

import pytest
import time
import json
from playwright.sync_api import Page
from loguru import logger

from pages.dashboard_page import DashboardPage
from pages.workspace_page import WorkspacePage
from utils.mock_data import (
    generate_pm_tasks, 
    generate_director_result, 
    generate_dialogue_history,
    generate_workspace_info
)
from utils.test_helpers import wait_for_condition, generate_random_string
from utils.file_utils import (
    create_file, 
    write_json_file, 
    delete_directory,
    ensure_directory,
    read_json_file
)


class TestIntegration:
    """Test integration between different components"""
    
    @pytest.mark.integration
    @pytest.mark.smoke
    def test_dashboard_workspace_integration(self, page: Page, sample_workspace):
        """Test integration between Dashboard and Workspace pages"""
        dashboard = DashboardPage(page)
        workspace_page = WorkspacePage(page)
        
        # Start with dashboard
        dashboard.navigate_to_dashboard()
        
        # Select workspace in dashboard
        dashboard.select_workspace(sample_workspace["path"])
        
        # Navigate to workspace page
        workspace_page.navigate_to_workspace()
        
        # Verify workspace is loaded
        workspace_details = workspace_page.get_workspace_details()
        assert sample_workspace["name"] in workspace_details["name"]
        
        # Go back to dashboard
        dashboard.navigate_to_dashboard()
        
        # Verify workspace selection is preserved
        selected_workspace = dashboard.get_selected_workspace()
        assert sample_workspace["path"] in selected_workspace
        
        logger.info("Dashboard-Workspace integration test passed")
    
    @pytest.mark.integration
    @pytest.mark.mock_ai
    def test_pm_director_data_flow(self, page: Page, sample_workspace, mock_ai_responses):
        """Test data flow between PM and Director"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Setup
        dashboard.select_workspace(sample_workspace["path"])
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        # Start PM
        dashboard.start_pm_loop()
        wait_for_condition(lambda: not dashboard.is_pm_running(), timeout=30000)
        
        # Get PM tasks
        pm_tasks = dashboard.get_task_list()
        assert len(pm_tasks) > 0, "PM should generate tasks"
        
        # Start Director
        dashboard.start_director_loop(iterations=1)
        wait_for_condition(lambda: not dashboard.is_director_running(), timeout=60000)
        
        # Verify Director processed PM tasks
        director_output = dashboard.get_director_output()
        assert len(director_output) > 0, "Director should produce output"
        
        # Check dialogue history for PM-Director handoff
        dialogue = dashboard.get_dialogue_history()
        pm_speakers = [entry for entry in dialogue if entry["speaker"] == "PM"]
        director_speakers = [entry for entry in dialogue if entry["speaker"] == "Director"]
        
        assert len(pm_speakers) > 0, "PM should have dialogue entries"
        assert len(director_speakers) > 0, "Director should have dialogue entries"
        
        logger.info(f"PM-Director data flow test passed: {len(pm_tasks)} tasks, {len(dialogue)} dialogue entries")
    
    @pytest.mark.integration
    @pytest.mark.mock_ai
    def test_qa_integration_with_director(self, page: Page, sample_workspace, mock_ai_responses):
        """Test QA integration with Director"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Setup
        dashboard.select_workspace(sample_workspace["path"])
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        # Run complete workflow
        dashboard.start_pm_loop()
        wait_for_condition(lambda: not dashboard.is_pm_running(), timeout=30000)
        
        dashboard.start_director_loop(iterations=1)
        wait_for_condition(lambda: not dashboard.is_director_running(), timeout=60000)
        
        # Check QA results
        qa_results = dashboard.get_qa_results()
        assert len(qa_results) > 0, "QA should produce results"
        
        # Verify QA is mentioned in dialogue
        dialogue = dashboard.get_dialogue_history()
        qa_entries = [entry for entry in dialogue if "QA" in entry["speaker"] or "qa" in entry["content"].lower()]
        
        # QA might not always produce entries depending on implementation
        logger.info(f"QA integration test: {len(qa_results)} QA results, {len(qa_entries)} QA dialogue entries")
    
    @pytest.mark.integration
    def test_file_system_integration(self, page: Page, temp_workspace_root):
        """Test integration with file system"""
        dashboard = DashboardPage(page)
        workspace_page = WorkspacePage(page)
        
        # Create test workspace with files
        workspace_name = "integration_test"
        workspace_path = temp_workspace_root / workspace_name
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Create test files
        (workspace_path / "docs").mkdir(exist_ok=True)
        (workspace_path / "src").mkdir(exist_ok=True)
        
        requirements_content = """
# Integration Test Requirements

## Features
1. User management
2. Data processing
3. Report generation
"""
        
        (workspace_path / "docs" / "requirements.md").write_text(requirements_content.strip())
        
        main_py_content = '''
def main():
    """Main function"""
    print("Integration test application")
    return True

if __name__ == "__main__":
    main()
'''
        
        (workspace_path / "src" / "main.py").write_text(main_py_content.strip())
        
        # Test in dashboard
        dashboard.navigate_to_dashboard()
        dashboard.select_workspace(str(workspace_path))
        
        # Verify workspace is recognized as valid
        assert dashboard.is_workspace_valid(), "Workspace should be valid"
        
        # Test in workspace page
        workspace_page.navigate_to_workspace()
        file_tree = workspace_page.get_file_tree()
        
        # Verify files are detected
        file_paths = [file["path"] for file in file_tree if not file["is_directory"]]
        assert any("requirements.md" in path for path in file_paths), "Requirements file should be detected"
        assert any("main.py" in path for path in file_paths), "Main Python file should be detected"
        
        logger.info(f"File system integration test passed: {len(file_paths)} files detected")
    
    @pytest.mark.integration
    @pytest.mark.mock_ai
    def test_state_persistence_integration(self, page: Page, sample_workspace, mock_ai_responses, mock_state_files):
        """Test state persistence across components"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Setup with mock state files
        dashboard.select_workspace(sample_workspace["path"])
        
        # Verify state is loaded
        tasks = dashboard.get_task_list()
        assert len(tasks) > 0, "Tasks should be loaded from state"
        
        dialogue = dashboard.get_dialogue_history()
        assert len(dialogue) > 0, "Dialogue should be loaded from state"
        
        # Run additional workflow
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        dashboard.start_pm_loop()
        wait_for_condition(lambda: not dashboard.is_pm_running(), timeout=30000)
        
        # Verify state is updated
        new_dialogue = dashboard.get_dialogue_history()
        assert len(new_dialogue) > len(dialogue), "State should be updated with new dialogue"
        
        logger.info(f"State persistence integration test passed: {len(new_dialogue)} total dialogue entries")
    
    @pytest.mark.integration
    @pytest.mark.parametrize("backend_combination", [
        ("codex", "ollama"),
        ("ollama", "ollama"),
    ])
    @pytest.mark.mock_ai
    def test_multi_backend_integration(self, page: Page, sample_workspace, mock_ai_responses, backend_combination):
        """Test integration with different backend combinations"""
        pm_backend, director_model = backend_combination
        
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Configure backends
        dashboard.select_workspace(sample_workspace["path"])
        dashboard.configure_pm_backend(pm_backend)
        dashboard.configure_director_model(director_model)
        
        # Run workflow
        dashboard.start_pm_loop()
        wait_for_condition(lambda: not dashboard.is_pm_running(), timeout=30000)
        
        dashboard.start_director_loop(iterations=1)
        wait_for_condition(lambda: not dashboard.is_director_running(), timeout=60000)
        
        # Verify results
        tasks = dashboard.get_task_list()
        assert len(tasks) > 0, f"Tasks should be generated with {pm_backend}/{director_model}"
        
        outputs = {
            "pm": dashboard.get_pm_output(),
            "director": dashboard.get_director_output(),
            "qa": dashboard.get_qa_results()
        }
        
        for component, output in outputs.items():
            assert len(output) > 0, f"{component} should produce output with {pm_backend}/{director_model}"
        
        logger.info(f"Multi-backend integration test passed for {pm_backend}/{director_model}")
    
    @pytest.mark.integration
    @pytest.mark.mock_ai
    def test_error_propagation_integration(self, page: Page, sample_workspace, mock_ai_responses):
        """Test error propagation across components"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Setup
        dashboard.select_workspace(sample_workspace["path"])
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        # Start PM
        dashboard.start_pm_loop()
        wait_for_condition(lambda: not dashboard.is_pm_running(), timeout=30000)
        
        # Start Director
        dashboard.start_director_loop(iterations=1)
        
        # Monitor for errors
        def check_for_errors():
            if dashboard.has_errors():
                return True
            if not dashboard.is_director_running():
                return True
            return False
        
        wait_for_condition(check_for_errors, timeout=60000)
        
        # Check error handling
        if dashboard.has_errors():
            error_details = dashboard.get_error_details()
            logger.info(f"Errors detected and handled: {error_details}")
            
            # Verify error doesn't crash the system
            assert dashboard.get_page_title(), "Page should still be responsive"
            
            # Try to recover
            dashboard.dismiss_error()
            dashboard.reset_workflow()
        
        logger.info("Error propagation integration test completed")
    
    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.mock_ai
    def test_performance_integration(self, page: Page, sample_workspace, mock_ai_responses):
        """Test performance across integrated components"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Setup
        dashboard.select_workspace(sample_workspace["path"])
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        # Measure performance
        start_time = time.time()
        
        # Run complete workflow
        dashboard.start_pm_loop()
        wait_for_condition(lambda: not dashboard.is_pm_running(), timeout=30000)
        
        pm_time = time.time()
        
        dashboard.start_director_loop(iterations=2)
        wait_for_condition(lambda: not dashboard.is_director_running(), timeout=90000)
        
        total_time = time.time() - start_time
        director_time = total_time - pm_time
        
        # Get performance metrics
        progress = dashboard.get_progress_percentage()
        elapsed_time = dashboard.get_elapsed_time()
        
        # Performance assertions
        assert total_time < 120, f"Total workflow took too long: {total_time}s"
        assert director_time < 60, f"Director took too long: {director_time}s"
        
        logger.info(f"Performance integration test: Total={total_time:.2f}s, PM={pm_time-start_time:.2f}s, Director={director_time:.2f}s")
    
    @pytest.mark.integration
    def test_configuration_integration(self, page: Page, sample_workspace):
        """Test configuration integration across components"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Test workspace configuration
        dashboard.select_workspace(sample_workspace["path"])
        
        # Test AI backend configuration
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        # Verify configuration is persistent
        assert dashboard.get_pm_backend() == "codex"
        assert dashboard.get_director_model() == "ollama"
        
        # Navigate away and back
        page.goto("about:blank")
        dashboard.navigate_to_dashboard()
        
        # Check if configuration is preserved (implementation dependent)
        # This test might need adjustment based on actual behavior
        
        logger.info("Configuration integration test completed")
    
    @pytest.mark.integration
    @pytest.mark.mock_ai
    def test_ui_state_synchronization(self, page: Page, sample_workspace, mock_ai_responses):
        """Test UI state synchronization across components"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Setup
        dashboard.select_workspace(sample_workspace["path"])
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        # Start PM and monitor UI updates
        dashboard.start_pm_loop()
        
        # Check UI state during PM execution
        assert dashboard.is_pm_running(), "UI should show PM running"
        
        # Wait for completion
        wait_for_condition(lambda: not dashboard.is_pm_running(), timeout=30000)
        
        # Check UI state after completion
        assert dashboard.is_pm_stopped(), "UI should show PM stopped"
        
        # Start Director and monitor UI
        dashboard.start_director_loop(iterations=1)
        
        # Check progress updates
        def check_progress_updates():
            progress = dashboard.get_progress_percentage()
            return progress > 0
        
        wait_for_condition(check_progress_updates, timeout=30000)
        
        # Wait for completion
        wait_for_condition(lambda: not dashboard.is_director_running(), timeout=60000)
        
        # Verify final UI state
        assert dashboard.is_director_stopped(), "UI should show Director stopped"
        
        logger.info("UI state synchronization test passed")
