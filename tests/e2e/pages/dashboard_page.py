"""
Dashboard page object for HarborPilot E2E tests
"""

from typing import Optional, List, Dict, Any
from playwright.sync_api import Page, Locator
from loguru import logger
import time

from .base_page import BasePage


class DashboardPage(BasePage):
    """Dashboard page with HarborPilot main interface"""
    
    def __init__(self, page: Page):
        super().__init__(page)
        self.page_url = "http://localhost:5173/dashboard"
    
    def get_base_url(self) -> str:
        """Get dashboard URL"""
        return self.page_url
    
    # ================================
    # Navigation
    # ================================
    
    def navigate_to_dashboard(self) -> None:
        """Navigate to dashboard page"""
        self.navigate(self.page_url)
        self.wait_for_page_load()
    
    # ================================
    # Workspace Selection
    # ================================
    
    def select_workspace(self, workspace_path: str) -> None:
        """Select a workspace directory"""
        logger.info(f"Selecting workspace: {workspace_path}")
        
        # Click workspace selector
        self.click("[data-testid='workspace-selector']")
        
        # Type workspace path
        self.type_text("[data-testid='workspace-input']", workspace_path)
        
        # Confirm selection
        self.click("[data-testid='workspace-confirm']")
        
        # Wait for workspace to load
        self.wait_for_loading_to_finish()
    
    def get_selected_workspace(self) -> str:
        """Get currently selected workspace path"""
        return self.get_text("[data-testid='selected-workspace']")
    
    def is_workspace_valid(self) -> bool:
        """Check if selected workspace is valid"""
        return not self.is_visible("[data-testid='workspace-error']", 2000)
    
    # ================================
    # AI Backend Configuration
    # ================================
    
    def configure_pm_backend(self, backend: str) -> None:
        """Configure PM backend (codex/ollama)"""
        logger.info(f"Configuring PM backend: {backend}")
        
        # Open PM backend dropdown
        self.click("[data-testid='pm-backend-selector']")
        
        # Select backend
        self.click(f"[data-testid='pm-backend-{backend}']")
        
        # Wait for configuration to apply
        self.wait_for_loading_to_finish()
    
    def configure_director_model(self, model: str) -> None:
        """Configure Director model"""
        logger.info(f"Configuring Director model: {model}")
        
        # Open Director model dropdown
        self.click("[data-testid='director-model-selector']")
        
        # Select model
        self.click(f"[data-testid='director-model-{model}']")
        
        # Wait for configuration to apply
        self.wait_for_loading_to_finish()
    
    def get_pm_backend(self) -> str:
        """Get current PM backend"""
        return self.get_attribute("[data-testid='pm-backend-selector']", "data-value") or ""
    
    def get_director_model(self) -> str:
        """Get current Director model"""
        return self.get_attribute("[data-testid='director-model-selector']", "data-value") or ""
    
    # ================================
    # PM Loop Control
    # ================================
    
    def start_pm_loop(self) -> None:
        """Start PM loop"""
        logger.info("Starting PM loop")
        
        # Ensure workspace is selected
        if not self.get_selected_workspace():
            raise Exception("Workspace must be selected before starting PM loop")
        
        # Click start button
        self.click("[data-testid='start-pm-button']")
        
        # Wait for PM to start
        self.wait_for_element("[data-testid='pm-status-running']", timeout=10000)
    
    def stop_pm_loop(self) -> None:
        """Stop PM loop"""
        logger.info("Stopping PM loop")
        
        self.click("[data-testid='stop-pm-button']")
        self.wait_for_element("[data-testid='pm-status-stopped']", timeout=10000)
    
    def is_pm_running(self) -> bool:
        """Check if PM loop is running"""
        return self.is_visible("[data-testid='pm-status-running']", 2000)
    
    def is_pm_stopped(self) -> bool:
        """Check if PM loop is stopped"""
        return self.is_visible("[data-testid='pm-status-stopped']", 2000)
    
    def get_pm_status(self) -> str:
        """Get PM status text"""
        if self.is_pm_running():
            return "running"
        elif self.is_pm_stopped():
            return "stopped"
        else:
            return "unknown"
    
    # ================================
    # Director Loop Control
    # ================================
    
    def start_director_loop(self, iterations: int = 1) -> None:
        """Start Director loop"""
        logger.info(f"Starting Director loop with {iterations} iterations")
        
        # Set iterations if needed
        if iterations > 1:
            self.type_text("[data-testid='director-iterations']", str(iterations))
        
        # Click start button
        self.click("[data-testid='start-director-button']")
        
        # Wait for Director to start
        self.wait_for_element("[data-testid='director-status-running']", timeout=10000)
    
    def stop_director_loop(self) -> None:
        """Stop Director loop"""
        logger.info("Stopping Director loop")
        
        self.click("[data-testid='stop-director-button']")
        self.wait_for_element("[data-testid='director-status-stopped']", timeout=10000)
    
    def is_director_running(self) -> bool:
        """Check if Director loop is running"""
        return self.is_visible("[data-testid='director-status-running']", 2000)
    
    def is_director_stopped(self) -> bool:
        """Check if Director loop is stopped"""
        return self.is_visible("[data-testid='director-status-stopped']", 2002)
    
    def get_director_status(self) -> str:
        """Get Director status text"""
        if self.is_director_running():
            return "running"
        elif self.is_director_stopped():
            return "stopped"
        else:
            return "unknown"
    
    # ================================
    # Task Management
    # ================================
    
    def get_task_list(self) -> List[Dict[str, str]]:
        """Get list of current tasks"""
        tasks = []
        task_elements = self.page.locator("[data-testid='task-item']")
        
        for i in range(task_elements.count()):
            element = task_elements.nth(i)
            task = {
                "id": self.get_attribute_from_element(element, "data-task-id"),
                "title": self.get_text_from_element(element, "[data-testid='task-title']"),
                "status": self.get_text_from_element(element, "[data-testid='task-status']"),
                "goal": self.get_text_from_element(element, "[data-testid='task-goal']")
            }
            tasks.append(task)
        
        return tasks
    
    def get_task_by_id(self, task_id: str) -> Optional[Dict[str, str]]:
        """Get specific task by ID"""
        tasks = self.get_task_list()
        for task in tasks:
            if task["id"] == task_id:
                return task
        return None
    
    def click_task(self, task_id: str) -> None:
        """Click on a specific task"""
        self.click(f"[data-testid='task-item'][data-task-id='{task_id}']")
    
    def expand_task_details(self, task_id: str) -> None:
        """Expand task details"""
        task_element = f"[data-testid='task-item'][data-task-id='{task_id}']"
        self.click(f"{task_element} [data-testid='expand-task']")
    
    def is_task_completed(self, task_id: str) -> bool:
        """Check if task is completed"""
        task_element = f"[data-testid='task-item'][data-task-id='{task_id}']"
        return self.is_visible(f"{task_element} [data-testid='task-status-completed']", 2000)
    
    # ================================
    # Results and Output
    # ================================
    
    def get_pm_output(self) -> str:
        """Get PM output text"""
        return self.get_text("[data-testid='pm-output']")
    
    def get_director_output(self) -> str:
        """Get Director output text"""
        return self.get_text("[data-testid='director-output']")
    
    def get_qa_results(self) -> str:
        """Get QA results text"""
        return self.get_text("[data-testid='qa-results']")
    
    def get_dialogue_history(self) -> List[Dict[str, str]]:
        """Get dialogue history"""
        dialogue_items = []
        dialogue_elements = self.page.locator("[data-testid='dialogue-item']")
        
        for i in range(dialogue_elements.count()):
            element = dialogue_elements.nth(i)
            item = {
                "timestamp": self.get_text_from_element(element, "[data-testid='dialogue-timestamp']"),
                "speaker": self.get_text_from_element(element, "[data-testid='dialogue-speaker']"),
                "content": self.get_text_from_element(element, "[data-testid='dialogue-content']")
            }
            dialogue_items.append(item)
        
        return dialogue_items
    
    # ================================
    # Status and Progress
    # ================================
    
    def get_progress_percentage(self) -> int:
        """Get overall progress percentage"""
        progress_text = self.get_text("[data-testid='progress-percentage']")
        # Extract number from text like "75%"
        import re
        match = re.search(r'(\d+)%', progress_text)
        return int(match.group(1)) if match else 0
    
    def get_current_phase(self) -> str:
        """Get current workflow phase"""
        return self.get_text("[data-testid='current-phase']")
    
    def get_elapsed_time(self) -> str:
        """Get elapsed time"""
        return self.get_text("[data-testid='elapsed-time']")
    
    # ================================
    # Error Handling
    # ================================
    
    def has_errors(self) -> bool:
        """Check if there are any errors"""
        return self.is_visible(self.error_message, 2000)
    
    def get_error_details(self) -> List[str]:
        """Get list of error messages"""
        errors = []
        error_elements = self.page.locator(self.error_message)
        
        for i in range(error_elements.count()):
            error_text = self.get_text_from_element(error_elements.nth(i))
            if error_text:
                errors.append(error_text)
        
        return errors
    
    def dismiss_error(self) -> None:
        """Dismiss error message"""
        if self.is_visible("[data-testid='dismiss-error']", 2000):
            self.click("[data-testid='dismiss-error']")
    
    # ================================
    # Utility Methods
    # ================================
    
    def wait_for_workflow_completion(self, timeout: int = 300000) -> None:
        """Wait for complete workflow to finish"""
        logger.info("Waiting for workflow completion")
        
        start_time = time.time()
        while time.time() - start_time < timeout / 1000:
            if not self.is_pm_running() and not self.is_director_running():
                logger.info("Workflow completed")
                return
            
            # Check for errors
            if self.has_errors():
                error_details = self.get_error_details()
                raise Exception(f"Workflow failed with errors: {error_details}")
            
            time.sleep(2)  # Poll every 2 seconds
        
        raise Exception(f"Workflow did not complete within {timeout}ms")
    
    def reset_workflow(self) -> None:
        """Reset the entire workflow"""
        logger.info("Resetting workflow")
        
        # Stop any running processes
        if self.is_pm_running():
            self.stop_pm_loop()
        if self.is_director_running():
            self.stop_director_loop()
        
        # Clear results
        self.click("[data-testid='clear-results']")
        
        # Wait for reset to complete
        self.wait_for_loading_to_finish()
    
    # ================================
    # Helper Methods
    # ================================
    
    def get_text_from_element(self, element: Locator, selector: Optional[str] = None) -> str:
        """Get text from element or its child"""
        if selector:
            return element.locator(selector).text_content() or ""
        return element.text_content() or ""
    
    def get_attribute_from_element(self, element: Locator, attribute: str) -> Optional[str]:
        """Get attribute from element"""
        return element.get_attribute(attribute)
    
    def is_element_in_element(self, element: Locator, selector: str, timeout: int = 2000) -> bool:
        """Check if element contains another element"""
        try:
            child = element.locator(selector)
            child.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False
