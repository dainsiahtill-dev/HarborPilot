"""
Workspace page object for HarborPilot E2E tests
"""

from typing import Optional, List, Dict, Any
from playwright.sync_api import Page, Locator
from loguru import logger

from .base_page import BasePage


class WorkspacePage(BasePage):
    """Workspace page for managing project workspaces"""
    
    def __init__(self, page: Page):
        super().__init__(page)
        self.page_url = "http://localhost:5173/workspace"
    
    def get_base_url(self) -> str:
        """Get workspace page URL"""
        return self.page_url
    
    # ================================
    # Navigation
    # ================================
    
    def navigate_to_workspace(self) -> None:
        """Navigate to workspace page"""
        self.navigate(self.page_url)
        self.wait_for_page_load()
    
    # ================================
    # Workspace Creation
    # ================================
    
    def create_new_workspace(self, name: str, path: str, project_type: str = "python") -> None:
        """Create a new workspace"""
        logger.info(f"Creating new workspace: {name} at {path}")
        
        # Click create workspace button
        self.click("[data-testid='create-workspace-button']")
        
        # Fill workspace details
        self.type_text("[data-testid='workspace-name-input']", name)
        self.type_text("[data-testid='workspace-path-input']", path)
        
        # Select project type
        self.select_option("[data-testid='project-type-select']", project_type)
        
        # Confirm creation
        self.click("[data-testid='confirm-create-workspace']")
        
        # Wait for creation to complete
        self.wait_for_loading_to_finish()
    
    def import_existing_workspace(self, path: str) -> None:
        """Import an existing workspace"""
        logger.info(f"Importing workspace from: {path}")
        
        # Click import workspace button
        self.click("[data-testid='import-workspace-button']")
        
        # Enter workspace path
        self.type_text("[data-testid='import-path-input']", path)
        
        # Confirm import
        self.click("[data-testid='confirm-import-workspace']")
        
        # Wait for import to complete
        self.wait_for_loading_to_finish()
    
    # ================================
    # Workspace List
    # ================================
    
    def get_workspace_list(self) -> List[Dict[str, str]]:
        """Get list of available workspaces"""
        workspaces = []
        workspace_elements = self.page.locator("[data-testid='workspace-item']")
        
        for i in range(workspace_elements.count()):
            element = workspace_elements.nth(i)
            workspace = {
                "name": self.get_text_from_element(element, "[data-testid='workspace-name']"),
                "path": self.get_text_from_element(element, "[data-testid='workspace-path']"),
                "type": self.get_text_from_element(element, "[data-testid='workspace-type']"),
                "status": self.get_text_from_element(element, "[data-testid='workspace-status']"),
                "last_modified": self.get_text_from_element(element, "[data-testid='workspace-last-modified']")
            }
            workspaces.append(workspace)
        
        return workspaces
    
    def get_workspace_by_name(self, name: str) -> Optional[Dict[str, str]]:
        """Get workspace by name"""
        workspaces = self.get_workspace_list()
        for workspace in workspaces:
            if workspace["name"] == name:
                return workspace
        return None
    
    def select_workspace_from_list(self, name: str) -> None:
        """Select a workspace from the list"""
        self.click(f"[data-testid='workspace-item'][data-workspace-name='{name}']")
    
    def delete_workspace(self, name: str, confirm: bool = True) -> None:
        """Delete a workspace"""
        logger.info(f"Deleting workspace: {name}")
        
        # Click delete button for the workspace
        self.click(f"[data-testid='workspace-item'][data-workspace-name='{name}'] [data-testid='delete-workspace']")
        
        # Confirm deletion if required
        if confirm:
            self.click("[data-testid='confirm-delete-workspace']")
        
        # Wait for deletion to complete
        self.wait_for_loading_to_finish()
    
    # ================================
    # Workspace Details
    # ================================
    
    def get_workspace_details(self) -> Dict[str, Any]:
        """Get details of the current workspace"""
        return {
            "name": self.get_text("[data-testid='current-workspace-name']"),
            "path": self.get_text("[data-testid='current-workspace-path']"),
            "type": self.get_text("[data-testid='current-workspace-type']"),
            "size": self.get_text("[data-testid='workspace-size']"),
            "file_count": self.get_text("[data-testid='workspace-file-count']"),
            "last_scan": self.get_text("[data-testid='workspace-last-scan']")
        }
    
    def scan_workspace(self) -> None:
        """Scan the current workspace for changes"""
        logger.info("Scanning workspace")
        
        self.click("[data-testid='scan-workspace-button']")
        self.wait_for_loading_to_finish()
    
    def refresh_workspace(self) -> None:
        """Refresh workspace information"""
        logger.info("Refreshing workspace")
        
        self.click("[data-testid='refresh-workspace-button']")
        self.wait_for_loading_to_finish()
    
    # ================================
    # File Management
    # ================================
    
    def get_file_tree(self) -> List[Dict[str, Any]]:
        """Get the file tree structure"""
        files = []
        file_elements = self.page.locator("[data-testid='file-tree-item']")
        
        for i in range(file_elements.count()):
            element = file_elements.nth(i)
            file_info = {
                "name": self.get_text_from_element(element, "[data-testid='file-name']"),
                "path": self.get_attribute_from_element(element, "data-file-path"),
                "type": self.get_attribute_from_element(element, "data-file-type"),
                "size": self.get_text_from_element(element, "[data-testid='file-size']"),
                "modified": self.get_text_from_element(element, "[data-testid='file-modified']"),
                "is_directory": self.get_attribute_from_element(element, "data-is-directory") == "true"
            }
            files.append(file_info)
        
        return files
    
    def expand_directory(self, path: str) -> None:
        """Expand a directory in the file tree"""
        self.click(f"[data-testid='file-tree-item'][data-file-path='{path}'] [data-testid='expand-directory']")
    
    def collapse_directory(self, path: str) -> None:
        """Collapse a directory in the file tree"""
        self.click(f"[data-testid='file-tree-item'][data-file-path='{path}'] [data-testid='collapse-directory']")
    
    def select_file(self, path: str) -> None:
        """Select a file in the file tree"""
        self.click(f"[data-testid='file-tree-item'][data-file-path='{path}']")
    
    def get_file_preview(self, path: str) -> str:
        """Get preview of a file"""
        # First select the file
        self.select_file(path)
        
        # Then get the preview content
        return self.get_text("[data-testid='file-preview-content']")
    
    def create_file(self, path: str, content: str = "") -> None:
        """Create a new file"""
        logger.info(f"Creating file: {path}")
        
        # Click create file button
        self.click("[data-testid='create-file-button']")
        
        # Enter file path
        self.type_text("[data-testid='new-file-path']", path)
        
        # Enter content if provided
        if content:
            self.type_text("[data-testid='new-file-content']", content)
        
        # Confirm creation
        self.click("[data-testid='confirm-create-file']")
        
        # Wait for creation to complete
        self.wait_for_loading_to_finish()
    
    def create_directory(self, path: str) -> None:
        """Create a new directory"""
        logger.info(f"Creating directory: {path}")
        
        # Click create directory button
        self.click("[data-testid='create-directory-button']")
        
        # Enter directory path
        self.type_text("[data-testid='new-directory-path']", path)
        
        # Confirm creation
        self.click("[data-testid='confirm-create-directory']")
        
        # Wait for creation to complete
        self.wait_for_loading_to_finish()
    
    def delete_file(self, path: str, confirm: bool = True) -> None:
        """Delete a file or directory"""
        logger.info(f"Deleting file: {path}")
        
        # Right-click on the file to open context menu
        self.page.locator(f"[data-testid='file-tree-item'][data-file-path='{path}']").click(button="right")
        
        # Click delete option
        self.click("[data-testid='context-menu-delete']")
        
        # Confirm deletion if required
        if confirm:
            self.click("[data-testid='confirm-delete-file']")
        
        # Wait for deletion to complete
        self.wait_for_loading_to_finish()
    
    # ================================
    # Workspace Settings
    # ================================
    
    def open_workspace_settings(self) -> None:
        """Open workspace settings"""
        self.click("[data-testid='workspace-settings-button']")
        self.wait_for_element("[data-testid='workspace-settings-dialog']")
    
    def close_workspace_settings(self) -> None:
        """Close workspace settings"""
        self.click("[data-testid='close-workspace-settings']")
    
    def set_workspace_description(self, description: str) -> None:
        """Set workspace description"""
        self.open_workspace_settings()
        self.type_text("[data-testid='workspace-description']", description)
        self.click("[data-testid='save-workspace-settings']")
        self.wait_for_loading_to_finish()
    
    def set_ignore_patterns(self, patterns: List[str]) -> None:
        """Set file ignore patterns"""
        self.open_workspace_settings()
        
        # Clear existing patterns
        self.click("[data-testid='clear-ignore-patterns']")
        
        # Add new patterns
        for pattern in patterns:
            self.type_text("[data-testid='new-ignore-pattern']", pattern)
            self.click("[data-testid='add-ignore-pattern']")
        
        # Save settings
        self.click("[data-testid='save-workspace-settings']")
        self.wait_for_loading_to_finish()
    
    def get_workspace_settings(self) -> Dict[str, Any]:
        """Get current workspace settings"""
        self.open_workspace_settings()
        
        settings = {
            "name": self.get_text("[data-testid='workspace-settings-name']"),
            "description": self.get_text("[data-testid='workspace-settings-description']"),
            "ignore_patterns": self.get_ignore_patterns(),
            "auto_scan": self.is_checked("[data-testid='auto-scan-enabled']"),
            "scan_interval": self.get_text("[data-testid='scan-interval']")
        }
        
        self.close_workspace_settings()
        return settings
    
    def get_ignore_patterns(self) -> List[str]:
        """Get current ignore patterns"""
        patterns = []
        pattern_elements = self.page.locator("[data-testid='ignore-pattern-item']")
        
        for i in range(pattern_elements.count()):
            pattern = self.get_text_from_element(pattern_elements.nth(i))
            if pattern:
                patterns.append(pattern)
        
        return patterns
    
    # ================================
    # Search and Filter
    # ================================
    
    def search_files(self, query: str) -> List[Dict[str, Any]]:
        """Search for files"""
        logger.info(f"Searching files with query: {query}")
        
        # Enter search query
        self.type_text("[data-testid='file-search-input']", query)
        
        # Wait for search results
        self.wait_for_loading_to_finish()
        
        # Get search results
        return self.get_file_tree()
    
    def filter_files_by_type(self, file_type: str) -> None:
        """Filter files by type"""
        self.select_option("[data-testid='file-type-filter']", file_type)
        self.wait_for_loading_to_finish()
    
    def clear_search(self) -> None:
        """Clear search and filters"""
        self.click("[data-testid='clear-search']")
        self.wait_for_loading_to_finish()
    
    # ================================
    # Validation
    # ================================
    
    def is_workspace_valid(self) -> bool:
        """Check if current workspace is valid"""
        return not self.is_visible("[data-testid='workspace-invalid']", 2000)
    
    def has_unsaved_changes(self) -> bool:
        """Check if workspace has unsaved changes"""
        return self.is_visible("[data-testid='unsaved-changes-indicator']", 2000)
    
    def get_validation_errors(self) -> List[str]:
        """Get workspace validation errors"""
        errors = []
        error_elements = self.page.locator("[data-testid='validation-error']")
        
        for i in range(error_elements.count()):
            error_text = self.get_text_from_element(error_elements.nth(i))
            if error_text:
                errors.append(error_text)
        
        return errors
    
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
    
    def is_checked(self, selector: str) -> bool:
        """Check if checkbox is checked"""
        element = self.page.locator(selector)
        return element.is_checked()
    
    def wait_for_workspace_load(self) -> None:
        """Wait for workspace to fully load"""
        self.wait_for_element("[data-testid='workspace-loaded']")
        self.wait_for_loading_to_finish()
