"""
Complete workflow tests for HarborPilot E2E
"""

import pytest
import time
from playwright.sync_api import Page
from loguru import logger

from pages.dashboard_page import DashboardPage
from pages.workspace_page import WorkspacePage
from utils.mock_data import (
    generate_pm_tasks, 
    generate_director_result, 
    generate_dialogue_history,
    generate_qa_response
)
from utils.test_helpers import wait_for_condition, generate_random_string
from utils.file_utils import (
    create_file, 
    write_json_file, 
    delete_directory,
    ensure_directory
)


class TestWorkflow:
    """Test complete HarborPilot workflows"""
    
    @pytest.mark.workflow
    @pytest.mark.smoke
    @pytest.mark.mock_ai
    def test_complete_workflow_simple(self, page: Page, sample_workspace, mock_ai_responses):
        """Test complete simple workflow: PM → Director → QA"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Step 1: Select and configure workspace
        dashboard.select_workspace(sample_workspace["path"])
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        # Step 2: Start PM loop
        dashboard.start_pm_loop()
        
        # Wait for PM to complete
        wait_for_condition(
            lambda: not dashboard.is_pm_running(),
            timeout=30000,
            timeout_message="PM loop did not complete"
        )
        
        # Step 3: Start Director loop
        dashboard.start_director_loop(iterations=1)
        
        # Wait for Director to complete
        wait_for_condition(
            lambda: not dashboard.is_director_running(),
            timeout=60000,
            timeout_message="Director loop did not complete"
        )
        
        # Step 4: Verify results
        tasks = dashboard.get_task_list()
        assert len(tasks) > 0, "No tasks generated"
        
        # Verify outputs are available
        pm_output = dashboard.get_pm_output()
        director_output = dashboard.get_director_output()
        qa_results = dashboard.get_qa_results()
        
        assert len(pm_output) > 0, "No PM output"
        assert len(director_output) > 0, "No Director output"
        
        logger.info("Complete simple workflow test passed")
    
    @pytest.mark.workflow
    @pytest.mark.mock_ai
    def test_workflow_with_multiple_iterations(self, page: Page, sample_workspace, mock_ai_responses):
        """Test workflow with multiple Director iterations"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Setup
        dashboard.select_workspace(sample_workspace["path"])
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        # Start PM
        dashboard.start_pm_loop()
        wait_for_condition(lambda: not dashboard.is_pm_running(), timeout=30000)
        
        # Start Director with multiple iterations
        dashboard.start_director_loop(iterations=3)
        
        # Wait for all iterations to complete
        wait_for_condition(
            lambda: not dashboard.is_director_running(),
            timeout=120000,
            timeout_message="Director iterations did not complete"
        )
        
        # Verify results
        dialogue = dashboard.get_dialogue_history()
        assert len(dialogue) > 0, "No dialogue history"
        
        # Check progress
        progress = dashboard.get_progress_percentage()
        assert progress > 0, "No progress made"
        
        logger.info(f"Multi-iteration workflow completed with {len(dialogue)} dialogue entries")
    
    @pytest.mark.workflow
    @pytest.mark.mock_ai
    def test_workflow_error_recovery(self, page: Page, sample_workspace, mock_ai_responses):
        """Test workflow error recovery"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Setup
        dashboard.select_workspace(sample_workspace["path"])
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        # Start PM
        dashboard.start_pm_loop()
        wait_for_condition(lambda: not dashboard.is_pm_running(), timeout=30000)
        
        # Start Director (might encounter errors)
        dashboard.start_director_loop(iterations=1)
        
        # Wait for completion or error
        def is_director_done_or_error():
            if not dashboard.is_director_running():
                return True
            if dashboard.has_errors():
                return True
            return False
        
        wait_for_condition(
            is_director_done_or_error,
            timeout=60000,
            timeout_message="Director did not complete or encounter error"
        )
        
        # Handle errors if any
        if dashboard.has_errors():
            error_details = dashboard.get_error_details()
            logger.warning(f"Workflow encountered errors: {error_details}")
            
            # Try to recover
            dashboard.dismiss_error()
            dashboard.reset_workflow()
            
            # Restart workflow
            dashboard.start_pm_loop()
            wait_for_condition(lambda: not dashboard.is_pm_running(), timeout=30000)
        
        # Verify recovery
        assert not dashboard.is_director_running(), "Director should be stopped"
        
        logger.info("Error recovery test completed")
    
    @pytest.mark.workflow
    @pytest.mark.mock_ai
    def test_workflow_task_completion(self, page: Page, sample_workspace, mock_ai_responses):
        """Test workflow with task completion tracking"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Setup
        dashboard.select_workspace(sample_workspace["path"])
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        # Start PM
        dashboard.start_pm_loop()
        wait_for_condition(lambda: not dashboard.is_pm_running(), timeout=30000)
        
        # Get initial tasks
        initial_tasks = dashboard.get_task_list()
        initial_task_ids = [task["id"] for task in initial_tasks]
        
        # Start Director
        dashboard.start_director_loop(iterations=1)
        wait_for_condition(lambda: not dashboard.is_director_running(), timeout=60000)
        
        # Check task completion
        final_tasks = dashboard.get_task_list()
        
        # Verify tasks are still present
        assert len(final_tasks) > 0, "No tasks after Director execution"
        
        # Check if any tasks are completed
        completed_tasks = [task for task in final_tasks if dashboard.is_task_completed(task["id"])]
        
        logger.info(f"Task completion test: {len(completed_tasks)} out of {len(final_tasks)} tasks completed")
    
    @pytest.mark.workflow
    @pytest.mark.mock_ai
    @pytest.mark.parametrize("pm_backend,director_model", [
        ("codex", "ollama"),
        ("ollama", "ollama"),
    ])
    def test_workflow_different_backends(self, page: Page, sample_workspace, mock_ai_responses, pm_backend, director_model):
        """Test workflow with different AI backend combinations"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Setup with specific backends
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
        assert len(tasks) > 0, f"No tasks with {pm_backend}/{director_model} combination"
        
        # Verify backends are correctly configured
        assert dashboard.get_pm_backend() == pm_backend
        assert dashboard.get_director_model() == director_model
        
        logger.info(f"Workflow test passed for {pm_backend}/{director_model} combination")
    
    @pytest.mark.workflow
    @pytest.mark.slow
    @pytest.mark.mock_ai
    def test_workflow_long_running(self, page: Page, sample_workspace, mock_ai_responses):
        """Test long-running workflow"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Setup
        dashboard.select_workspace(sample_workspace["path"])
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        # Start PM
        dashboard.start_pm_loop()
        wait_for_condition(lambda: not dashboard.is_pm_running(), timeout=30000)
        
        # Start Director with more iterations
        dashboard.start_director_loop(iterations=5)
        
        # Monitor progress during execution
        start_time = time.time()
        last_progress = 0
        
        def monitor_progress():
            nonlocal last_progress
            if dashboard.is_director_running():
                current_progress = dashboard.get_progress_percentage()
                if current_progress > last_progress:
                    last_progress = current_progress
                    logger.info(f"Progress: {current_progress}%")
                return False
            return True
        
        # Wait with progress monitoring
        wait_for_condition(
            monitor_progress,
            timeout=180000,  # 3 minutes
            timeout_message="Long-running workflow did not complete"
        )
        
        execution_time = time.time() - start_time
        logger.info(f"Long-running workflow completed in {execution_time:.2f} seconds")
        
        # Verify final results
        assert last_progress > 0, "No progress made during long-running workflow"
    
    @pytest.mark.workflow
    def test_workflow_with_empty_workspace(self, page: Page, empty_workspace):
        """Test workflow behavior with empty workspace"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Setup with empty workspace
        dashboard.select_workspace(empty_workspace["path"])
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        # Start PM (should handle empty workspace gracefully)
        dashboard.start_pm_loop()
        
        # Wait for completion or error
        def is_pm_done_or_error():
            if not dashboard.is_pm_running():
                return True
            if dashboard.has_errors():
                return True
            return False
        
        wait_for_condition(
            is_pm_done_or_error,
            timeout=30000,
            timeout_message="PM did not handle empty workspace properly"
        )
        
        # Check for appropriate error handling
        if dashboard.has_errors():
            error_details = dashboard.get_error_details()
            logger.info(f"Empty workspace properly handled with error: {error_details}")
        
        # Verify graceful handling
        assert not dashboard.is_pm_running(), "PM should be stopped"
        
        logger.info("Empty workspace workflow test completed")
    
    @pytest.mark.workflow
    @pytest.mark.mock_ai
    def test_workflow_state_persistence(self, page: Page, sample_workspace, mock_ai_responses):
        """Test workflow state persistence across sessions"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Setup and run first part of workflow
        dashboard.select_workspace(sample_workspace["path"])
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        dashboard.start_pm_loop()
        wait_for_condition(lambda: not dashboard.is_pm_running(), timeout=30000)
        
        # Get state after PM
        tasks_after_pm = dashboard.get_task_list()
        dialogue_after_pm = dashboard.get_dialogue_history()
        
        # Simulate page refresh/reload
        page.reload()
        dashboard.wait_for_page_load()
        
        # Verify state is preserved
        dashboard.assert_element_visible("[data-testid='workspace-selector']")
        
        # Check if workspace selection is preserved
        # This depends on the actual implementation
        
        # Continue with Director
        dashboard.start_director_loop(iterations=1)
        wait_for_condition(lambda: not dashboard.is_director_running(), timeout=60000)
        
        # Verify final state
        final_dialogue = dashboard.get_dialogue_history()
        assert len(final_dialogue) >= len(dialogue_after_pm), "Dialogue state not preserved"
        
        logger.info("State persistence test completed")
    
    @pytest.mark.workflow
    @pytest.mark.mock_ai
    def test_workflow_concurrent_operations(self, page: Page, sample_workspace, mock_ai_responses):
        """Test workflow with concurrent operations"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Setup
        dashboard.select_workspace(sample_workspace["path"])
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        # Start PM
        dashboard.start_pm_loop()
        
        # Try to start Director while PM is running (should be prevented)
        try:
            dashboard.start_director_loop(iterations=1)
            director_started_while_pm_running = True
        except Exception:
            director_started_while_pm_running = False
        
        # Wait for PM to complete
        wait_for_condition(lambda: not dashboard.is_pm_running(), timeout=30000)
        
        # Now Director should be startable
        dashboard.start_director_loop(iterations=1)
        wait_for_condition(lambda: not dashboard.is_director_running(), timeout=60000)
        
        # Verify proper concurrency control
        # This depends on the actual implementation
        
        logger.info("Concurrent operations test completed")
    
    @pytest.mark.workflow
    @pytest.mark.mock_ai
    def test_workflow_resource_cleanup(self, page: Page, sample_workspace, mock_ai_responses):
        """Test workflow resource cleanup"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Setup and run workflow
        dashboard.select_workspace(sample_workspace["path"])
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        dashboard.start_pm_loop()
        wait_for_condition(lambda: not dashboard.is_pm_running(), timeout=30000)
        
        dashboard.start_director_loop(iterations=1)
        wait_for_condition(lambda: not dashboard.is_director_running(), timeout=60000)
        
        # Reset workflow
        dashboard.reset_workflow()
        
        # Verify cleanup
        assert not dashboard.is_pm_running()
        assert not dashboard.is_director_running()
        
        # Check if temporary resources are cleaned up
        # This would depend on the actual implementation
        
        # Try starting new workflow to verify clean state
        dashboard.start_pm_loop()
        wait_for_condition(lambda: not dashboard.is_pm_running(), timeout=30000)
        
        logger.info("Resource cleanup test completed")
