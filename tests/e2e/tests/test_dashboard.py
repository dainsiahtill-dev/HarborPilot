"""
Dashboard functionality tests for HarborPilot E2E
"""

import pytest
import time
from playwright.sync_api import Page
from loguru import logger

from pages.dashboard_page import DashboardPage
from pages.workspace_page import WorkspacePage
from utils.mock_data import generate_pm_tasks, generate_director_result, generate_dialogue_history
from utils.test_helpers import wait_for_condition, generate_random_string
from utils.file_utils import create_file, write_json_file, delete_directory


class TestDashboard:
    """Test Dashboard functionality"""
    
    @pytest.mark.smoke
    @pytest.mark.dashboard
    def test_dashboard_loads_successfully(self, page: Page, test_config):
        """Test that dashboard loads successfully"""
        dashboard = DashboardPage(page)
        
        # Navigate to dashboard
        dashboard.navigate_to_dashboard()
        
        # Verify page title
        assert "HarborPilot" in dashboard.get_page_title()
        
        # Verify main elements are present
        dashboard.assert_element_visible("[data-testid='workspace-selector']")
        dashboard.assert_element_visible("[data-testid='pm-backend-selector']")
        dashboard.assert_element_visible("[data-testid='director-model-selector']")
        
        logger.info("Dashboard loaded successfully")
    
    @pytest.mark.dashboard
    def test_workspace_selection(self, page: Page, sample_workspace):
        """Test workspace selection functionality"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Select workspace
        dashboard.select_workspace(sample_workspace["path"])
        
        # Verify workspace is selected
        selected_workspace = dashboard.get_selected_workspace()
        assert sample_workspace["path"] in selected_workspace
        
        # Verify workspace is valid
        assert dashboard.is_workspace_valid()
        
        logger.info(f"Successfully selected workspace: {sample_workspace['path']}")
    
    @pytest.mark.dashboard
    def test_workspace_selection_invalid(self, page: Page):
        """Test workspace selection with invalid path"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Try to select invalid workspace
        invalid_path = "/nonexistent/path"
        dashboard.select_workspace(invalid_path)
        
        # Verify error is shown
        assert not dashboard.is_workspace_valid()
        
        logger.info("Invalid workspace properly rejected")
    
    @pytest.mark.dashboard
    @pytest.mark.parametrize("backend", ["codex", "ollama"])
    def test_pm_backend_configuration(self, page: Page, backend):
        """Test PM backend configuration"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Configure PM backend
        dashboard.configure_pm_backend(backend)
        
        # Verify configuration
        current_backend = dashboard.get_pm_backend()
        assert current_backend == backend
        
        logger.info(f"Successfully configured PM backend: {backend}")
    
    @pytest.mark.dashboard
    @pytest.mark.parametrize("model", ["llama2", "codellama", "mistral"])
    def test_director_model_configuration(self, page: Page, model):
        """Test Director model configuration"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Configure Director model
        dashboard.configure_director_model(model)
        
        # Verify configuration
        current_model = dashboard.get_director_model()
        assert current_model == model
        
        logger.info(f"Successfully configured Director model: {model}")
    
    @pytest.mark.dashboard
    @pytest.mark.mock_ai
    def test_pm_loop_start_stop(self, page: Page, sample_workspace, mock_ai_responses):
        """Test PM loop start and stop functionality"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Select workspace
        dashboard.select_workspace(sample_workspace["path"])
        
        # Configure backends
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        # Start PM loop
        dashboard.start_pm_loop()
        
        # Verify PM is running
        assert dashboard.is_pm_running()
        assert dashboard.get_pm_status() == "running"
        
        # Wait a bit for processing
        time.sleep(2)
        
        # Stop PM loop
        dashboard.stop_pm_loop()
        
        # Verify PM is stopped
        assert dashboard.is_pm_stopped()
        assert dashboard.get_pm_status() == "stopped"
        
        logger.info("PM loop start/stop test completed successfully")
    
    @pytest.mark.dashboard
    @pytest.mark.mock_ai
    def test_director_loop_start_stop(self, page: Page, sample_workspace, mock_ai_responses):
        """Test Director loop start and stop functionality"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Select workspace and configure
        dashboard.select_workspace(sample_workspace["path"])
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        # Start Director loop
        dashboard.start_director_loop(iterations=1)
        
        # Verify Director is running
        assert dashboard.is_director_running()
        assert dashboard.get_director_status() == "running"
        
        # Wait a bit for processing
        time.sleep(2)
        
        # Stop Director loop
        dashboard.stop_director_loop()
        
        # Verify Director is stopped
        assert dashboard.is_director_stopped()
        assert dashboard.get_director_status() == "stopped"
        
        logger.info("Director loop start/stop test completed successfully")
    
    @pytest.mark.dashboard
    def test_task_display(self, page: Page, mock_state_files):
        """Test task display functionality"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Load mock state files
        # This would typically be done by setting up the workspace with state files
        
        # Get task list
        tasks = dashboard.get_task_list()
        
        # Verify tasks are displayed
        assert len(tasks) > 0
        
        # Verify task structure
        for task in tasks:
            assert "id" in task
            assert "title" in task
            assert "status" in task
            assert "goal" in task
        
        logger.info(f"Successfully displayed {len(tasks)} tasks")
    
    @pytest.mark.dashboard
    def test_task_interaction(self, page: Page, mock_state_files):
        """Test task interaction functionality"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Get tasks
        tasks = dashboard.get_task_list()
        
        if tasks:
            first_task = tasks[0]
            task_id = first_task["id"]
            
            # Click on task
            dashboard.click_task(task_id)
            
            # Expand task details
            dashboard.expand_task_details(task_id)
            
            # Verify task details are visible
            # This would depend on the actual UI implementation
            
            logger.info(f"Successfully interacted with task: {task_id}")
    
    @pytest.mark.dashboard
    def test_output_display(self, page: Page, mock_state_files):
        """Test output display functionality"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Get PM output
        pm_output = dashboard.get_pm_output()
        
        # Get Director output
        director_output = dashboard.get_director_output()
        
        # Get QA results
        qa_results = dashboard.get_qa_results()
        
        # Verify outputs are accessible
        # The actual content would depend on mock data
        assert isinstance(pm_output, str)
        assert isinstance(director_output, str)
        assert isinstance(qa_results, str)
        
        logger.info("Output display test completed successfully")
    
    @pytest.mark.dashboard
    def test_dialogue_history(self, page: Page, mock_state_files):
        """Test dialogue history display"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Get dialogue history
        dialogue = dashboard.get_dialogue_history()
        
        # Verify dialogue structure
        for entry in dialogue:
            assert "timestamp" in entry
            assert "speaker" in entry
            assert "content" in entry
        
        logger.info(f"Successfully displayed {len(dialogue)} dialogue entries")
    
    @pytest.mark.dashboard
    def test_progress_indicators(self, page: Page):
        """Test progress indicators"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Get progress percentage
        progress = dashboard.get_progress_percentage()
        assert isinstance(progress, int)
        assert 0 <= progress <= 100
        
        # Get current phase
        phase = dashboard.get_current_phase()
        assert isinstance(phase, str)
        
        # Get elapsed time
        elapsed_time = dashboard.get_elapsed_time()
        assert isinstance(elapsed_time, str)
        
        logger.info(f"Progress: {progress}%, Phase: {phase}, Time: {elapsed_time}")
    
    @pytest.mark.dashboard
    def test_error_handling(self, page: Page):
        """Test error handling and display"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Initially should have no errors
        assert not dashboard.has_errors()
        
        # Try to start PM without workspace (should cause error)
        try:
            dashboard.start_pm_loop()
        except Exception:
            pass  # Expected to fail
        
        # Check for errors
        # This depends on how the application handles errors
        if dashboard.has_errors():
            error_details = dashboard.get_error_details()
            assert len(error_details) > 0
            
            # Dismiss error
            dashboard.dismiss_error()
            
        logger.info("Error handling test completed")
    
    @pytest.mark.dashboard
    @pytest.mark.slow
    def test_workflow_reset(self, page: Page, sample_workspace):
        """Test workflow reset functionality"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Select workspace and configure
        dashboard.select_workspace(sample_workspace["path"])
        dashboard.configure_pm_backend("codex")
        dashboard.configure_director_model("ollama")
        
        # Start some processes
        try:
            dashboard.start_pm_loop()
            time.sleep(1)
        except Exception:
            pass
        
        # Reset workflow
        dashboard.reset_workflow()
        
        # Verify everything is stopped
        assert not dashboard.is_pm_running()
        assert not dashboard.is_director_running()
        
        logger.info("Workflow reset test completed successfully")
    
    @pytest.mark.dashboard
    def test_responsive_design(self, page: Page, test_config):
        """Test responsive design on different viewports"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Test different viewport sizes
        viewports = [
            {"width": 1920, "height": 1080},  # Desktop
            {"width": 1366, "height": 768},   # Laptop
            {"width": 768, "height": 1024},   # Tablet
            {"width": 375, "height": 667}     # Mobile
        ]
        
        for viewport in viewports:
            page.set_viewport_size(viewport)
            
            # Wait for layout to adjust
            page.wait_for_timeout(1000)
            
            # Verify key elements are still visible
            dashboard.assert_element_visible("[data-testid='workspace-selector']")
            
            logger.info(f"Responsive design test passed for viewport: {viewport}")
    
    @pytest.mark.dashboard
    @pytest.mark.regression
    def test_keyboard_navigation(self, page: Page, sample_workspace):
        """Test keyboard navigation"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Test Tab navigation
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")
        
        # Test Enter key on focused element
        page.keyboard.press("Enter")
        
        # Test Escape key
        page.keyboard.press("Escape")
        
        logger.info("Keyboard navigation test completed")
    
    @pytest.mark.dashboard
    def test_accessibility_features(self, page: Page):
        """Test accessibility features"""
        dashboard = DashboardPage(page)
        dashboard.navigate_to_dashboard()
        
        # Check for ARIA labels
        workspace_selector = page.locator("[data-testid='workspace-selector']")
        aria_label = workspace_selector.get_attribute("aria-label")
        assert aria_label is not None
        
        # Check for proper heading structure
        headings = page.locator("h1, h2, h3, h4, h5, h6")
        assert headings.count() > 0
        
        # Check for alt text on images (if any)
        images = page.locator("img")
        for i in range(images.count()):
            img = images.nth(i)
            alt_text = img.get_attribute("alt")
            if alt_text is None:
                logger.warning(f"Image missing alt text: {img.get_attribute('src')}")
        
        logger.info("Accessibility features test completed")
