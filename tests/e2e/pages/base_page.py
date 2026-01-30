"""
Base page class for HarborPilot E2E tests
"""

from typing import Optional, Dict, Any
from playwright.sync_api import Page, Locator, expect
from loguru import logger


class BasePage:
    """Base page with common functionality for all pages"""
    
    def __init__(self, page: Page):
        self.page = page
        self.timeout = 30000  # Default timeout in milliseconds
        
    # ================================
    # Navigation Methods
    # ================================
    
    def navigate(self, url: Optional[str] = None) -> None:
        """Navigate to a URL"""
        target_url = url or self.get_base_url()
        logger.info(f"Navigating to: {target_url}")
        self.page.goto(target_url, timeout=self.timeout)
        
    def get_base_url(self) -> str:
        """Get base URL for the page"""
        return "http://localhost:5173"
    
    def reload(self) -> None:
        """Reload the current page"""
        logger.info("Reloading page")
        self.page.reload(timeout=self.timeout)
    
    # ================================
    # Wait Methods
    # ================================
    
    def wait_for_page_load(self, timeout: Optional[int] = None) -> None:
        """Wait for page to fully load"""
        timeout = timeout or self.timeout
        self.page.wait_for_load_state("networkidle", timeout=timeout)
        
    def wait_for_element(self, selector: str, timeout: Optional[int] = None) -> Locator:
        """Wait for element to be visible"""
        timeout = timeout or self.timeout
        locator = self.page.locator(selector)
        locator.wait_for(state="visible", timeout=timeout)
        return locator
    
    def wait_for_element_to_disappear(self, selector: str, timeout: Optional[int] = None) -> None:
        """Wait for element to disappear"""
        timeout = timeout or self.timeout
        locator = self.page.locator(selector)
        locator.wait_for(state="hidden", timeout=timeout)
    
    # ================================
    # Element Interaction Methods
    # ================================
    
    def click(self, selector: str, timeout: Optional[int] = None) -> None:
        """Click on an element"""
        logger.info(f"Clicking element: {selector}")
        element = self.wait_for_element(selector, timeout)
        element.click(timeout=timeout)
        
    def type_text(self, selector: str, text: str, clear: bool = True, timeout: Optional[int] = None) -> None:
        """Type text into an input field"""
        logger.info(f"Typing text into {selector}: {text}")
        element = self.wait_for_element(selector, timeout)
        
        if clear:
            element.clear()
            
        element.fill(text, timeout=timeout)
        
    def get_text(self, selector: str, timeout: Optional[int] = None) -> str:
        """Get text content of an element"""
        element = self.wait_for_element(selector, timeout)
        return element.text_content() or ""
    
    def get_attribute(self, selector: str, attribute: str, timeout: Optional[int] = None) -> Optional[str]:
        """Get attribute value of an element"""
        element = self.wait_for_element(selector, timeout)
        return element.get_attribute(attribute)
    
    def is_visible(self, selector: str, timeout: int = 5000) -> bool:
        """Check if element is visible"""
        try:
            element = self.page.locator(selector)
            element.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False
    
    def is_enabled(self, selector: str, timeout: int = 5000) -> bool:
        """Check if element is enabled"""
        try:
            element = self.wait_for_element(selector, timeout)
            return element.is_enabled()
        except Exception:
            return False
    
    # ================================
    # Selection Methods
    # ================================
    
    def select_option(self, selector: str, value: str, timeout: Optional[int] = None) -> None:
        """Select option from dropdown"""
        logger.info(f"Selecting option '{value}' from {selector}")
        element = self.wait_for_element(selector, timeout)
        element.select_option(value=value, timeout=timeout)
        
    def check_checkbox(self, selector: str, timeout: Optional[int] = None) -> None:
        """Check a checkbox"""
        logger.info(f"Checking checkbox: {selector}")
        element = self.wait_for_element(selector, timeout)
        element.check(timeout=timeout)
        
    def uncheck_checkbox(self, selector: str, timeout: Optional[int] = None) -> None:
        """Uncheck a checkbox"""
        logger.info(f"Unchecking checkbox: {selector}")
        element = self.wait_for_element(selector, timeout)
        element.uncheck(timeout=timeout)
    
    # ================================
    # Assertion Methods
    # ================================
    
    def assert_text_equals(self, selector: str, expected_text: str, timeout: Optional[int] = None) -> None:
        """Assert element text equals expected text"""
        element = self.wait_for_element(selector, timeout)
        expect(element).to_have_text(expected_text, timeout=timeout)
        
    def assert_text_contains(self, selector: str, expected_text: str, timeout: Optional[int] = None) -> None:
        """Assert element text contains expected text"""
        element = self.wait_for_element(selector, timeout)
        expect(element).to_contain_text(expected_text, timeout=timeout)
        
    def assert_element_visible(self, selector: str, timeout: Optional[int] = None) -> None:
        """Assert element is visible"""
        element = self.page.locator(selector)
        expect(element).to_be_visible(timeout=timeout)
        
    def assert_element_hidden(self, selector: str, timeout: Optional[int] = None) -> None:
        """Assert element is hidden"""
        element = self.page.locator(selector)
        expect(element).to_be_hidden(timeout=timeout)
        
    def assert_element_enabled(self, selector: str, timeout: Optional[int] = None) -> None:
        """Assert element is enabled"""
        element = self.page.locator(selector)
        expect(element).to_be_enabled(timeout=timeout)
        
    def assert_element_disabled(self, selector: str, timeout: Optional[int] = None) -> None:
        """Assert element is disabled"""
        element = self.page.locator(selector)
        expect(element).to_be_disabled(timeout=timeout)
    
    # ================================
    # Utility Methods
    # ================================
    
    def take_screenshot(self, filename: str, full_page: bool = True) -> str:
        """Take screenshot of the page"""
        screenshot_path = f"reports/screenshots/{filename}"
        self.page.screenshot(path=screenshot_path, full_page=full_page)
        logger.info(f"Screenshot saved: {screenshot_path}")
        return screenshot_path
    
    def wait_for_api_response(self, url_pattern: str, timeout: int = 30000) -> Dict[str, Any]:
        """Wait for specific API response"""
        logger.info(f"Waiting for API response: {url_pattern}")
        
        with self.page.expect_response(url_pattern, timeout=timeout) as response_info:
            response = response_info.value
            return {
                "status": response.status,
                "url": response.url,
                "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text()
            }
    
    def execute_javascript(self, script: str, *args) -> Any:
        """Execute JavaScript in the page context"""
        return self.page.evaluate(script, *args)
    
    def get_page_title(self) -> str:
        """Get page title"""
        return self.page.title()
    
    def get_current_url(self) -> str:
        """Get current URL"""
        return self.page.url
    
    # ================================
    # Error Handling
    # ================================
    
    def handle_error(self, error: Exception, context: str = "") -> None:
        """Handle errors with logging and screenshots"""
        error_msg = f"Error in {context}: {str(error)}" if context else str(error)
        logger.error(error_msg)
        
        # Take screenshot for debugging
        timestamp = int(time.time())
        screenshot_name = f"error_{context}_{timestamp}.png"
        self.take_screenshot(screenshot_name)
        
        raise Exception(error_msg)
    
    # ================================
    # Common Selectors
    # ================================
    
    @property
    def loading_spinner(self) -> str:
        """Common loading spinner selector"""
        return "[data-testid='loading-spinner'], .loading, .spinner"
    
    @property
    def error_message(self) -> str:
        """Common error message selector"""
        return "[data-testid='error-message'], .error, .alert-error"
    
    @property
    def success_message(self) -> str:
        """Common success message selector"""
        return "[data-testid='success-message'], .success, .alert-success"
    
    @property
    def button_primary(self) -> str:
        """Primary button selector"""
        return "[data-testid='btn-primary'], .btn-primary, button[type='submit']"
    
    @property
    def button_secondary(self) -> str:
        """Secondary button selector"""
        return "[data-testid='btn-secondary'], .btn-secondary"
    
    def wait_for_loading_to_finish(self, timeout: Optional[int] = None) -> None:
        """Wait for loading spinners to disappear"""
        timeout = timeout or self.timeout
        try:
            self.wait_for_element_to_disappear(self.loading_spinner, timeout)
        except Exception:
            # Loading spinner might not exist, continue
            pass
    
    def get_error_message_text(self) -> str:
        """Get error message text if present"""
        if self.is_visible(self.error_message, 2000):
            return self.get_text(self.error_message)
        return ""
    
    def get_success_message_text(self) -> str:
        """Get success message text if present"""
        if self.is_visible(self.success_message, 2000):
            return self.get_text(self.success_message)
        return ""
