"""
Test helper utilities for HarborPilot E2E tests
"""

import time
import random
import string
from typing import Any, Callable, Optional, Dict, List
from pathlib import Path
from loguru import logger


class TestHelper:
    """Helper class for common test operations"""
    
    @staticmethod
    def wait_for_condition(
        condition: Callable[[], bool],
        timeout: int = 30000,
        poll_interval: int = 500,
        timeout_message: str = "Condition not met within timeout"
    ) -> bool:
        """
        Wait for a condition to be true
        
        Args:
            condition: Function that returns boolean
            timeout: Maximum wait time in milliseconds
            poll_interval: Poll interval in milliseconds
            timeout_message: Custom timeout message
            
        Returns:
            True if condition was met, False otherwise
        """
        start_time = time.time()
        timeout_seconds = timeout / 1000
        poll_interval_seconds = poll_interval / 1000
        
        while time.time() - start_time < timeout_seconds:
            try:
                if condition():
                    return True
            except Exception as e:
                logger.warning(f"Error checking condition: {e}")
            
            time.sleep(poll_interval_seconds)
        
        logger.error(timeout_message)
        return False
    
    @staticmethod
    def wait_for_api_call(
        api_call: Callable[[], Any],
        expected_result: Any = None,
        timeout: int = 30000,
        poll_interval: int = 1000
    ) -> Any:
        """
        Wait for API call to return expected result
        
        Args:
            api_call: Function that makes API call
            expected_result: Expected result value
            timeout: Maximum wait time in milliseconds
            poll_interval: Poll interval in milliseconds
            
        Returns:
            API call result
        """
        def condition():
            try:
                result = api_call()
                if expected_result is None:
                    return result is not None
                return result == expected_result
            except Exception:
                return False
        
        if TestHelper.wait_for_condition(condition, timeout, poll_interval):
            return api_call()
        
        raise Exception(f"API call did not return expected result within {timeout}ms")
    
    @staticmethod
    def retry_on_failure(
        func: Callable,
        max_attempts: int = 3,
        delay: int = 1000,
        exceptions: tuple = (Exception,)
    ) -> Any:
        """
        Retry a function on failure
        
        Args:
            func: Function to retry
            max_attempts: Maximum number of attempts
            delay: Delay between attempts in milliseconds
            exceptions: Exceptions to catch and retry on
            
        Returns:
            Function result
            
        Raises:
            Last exception if all attempts fail
        """
        last_exception = None
        
        for attempt in range(max_attempts):
            try:
                return func()
            except exceptions as e:
                last_exception = e
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                
                if attempt < max_attempts - 1:
                    time.sleep(delay / 1000)
        
        raise last_exception
    
    @staticmethod
    def generate_random_string(length: int = 10, include_numbers: bool = True) -> str:
        """
        Generate random string
        
        Args:
            length: String length
            include_numbers: Whether to include numbers
            
        Returns:
            Random string
        """
        chars = string.ascii_letters
        if include_numbers:
            chars += string.digits
        
        return ''.join(random.choice(chars) for _ in range(length))
    
    @staticmethod
    def generate_random_email() -> str:
        """Generate random email address"""
        username = TestHelper.generate_random_string(8, include_numbers=False).lower()
        domain = TestHelper.generate_random_string(6, include_numbers=False).lower()
        return f"{username}@{domain}.com"
    
    @staticmethod
    def generate_random_phone() -> str:
        """Generate random phone number"""
        return f"+1{random.randint(1000000000, 9999999999)}"
    
    @staticmethod
    def get_timestamp() -> str:
        """Get current timestamp as string"""
        return str(int(time.time()))
    
    @staticmethod
    def get_datetime_string() -> str:
        """Get current datetime as formatted string"""
        return time.strftime("%Y-%m-%d_%H-%M-%S")
    
    @staticmethod
    def format_bytes(bytes_count: int) -> str:
        """Format bytes into human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.1f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.1f} TB"
    
    @staticmethod
    def parse_duration(duration_str: str) -> int:
        """Parse duration string to milliseconds"""
        duration_str = duration_str.lower().strip()
        
        if duration_str.endswith('ms'):
            return int(duration_str[:-2])
        elif duration_str.endswith('s'):
            return int(duration_str[:-1]) * 1000
        elif duration_str.endswith('m'):
            return int(duration_str[:-1]) * 60 * 1000
        elif duration_str.endswith('h'):
            return int(duration_str[:-1]) * 60 * 60 * 1000
        else:
            # Assume seconds if no unit
            return int(duration_str) * 1000
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe file system usage"""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Remove leading/trailing spaces and dots
        filename = filename.strip(' .')
        
        # Ensure filename is not empty
        if not filename:
            filename = f"file_{TestHelper.get_timestamp()}"
        
        return filename
    
    @staticmethod
    def compare_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any], ignore_keys: List[str] = None) -> bool:
        """
        Compare two dictionaries, optionally ignoring certain keys
        
        Args:
            dict1: First dictionary
            dict2: Second dictionary
            ignore_keys: List of keys to ignore during comparison
            
        Returns:
            True if dictionaries are equal (ignoring specified keys)
        """
        if ignore_keys is None:
            ignore_keys = []
        
        # Create copies without ignored keys
        d1 = {k: v for k, v in dict1.items() if k not in ignore_keys}
        d2 = {k: v for k, v in dict2.items() if k not in ignore_keys}
        
        return d1 == d2
    
    @staticmethod
    def extract_numbers_from_string(text: str) -> List[int]:
        """Extract all numbers from a string"""
        import re
        numbers = re.findall(r'\d+', text)
        return [int(num) for num in numbers]
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Check if string is a valid URL"""
        import re
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return url_pattern.match(url) is not None
    
    @staticmethod
    def create_test_data_directory(base_path: str, test_name: str) -> Path:
        """
        Create test data directory
        
        Args:
            base_path: Base path for test data
            test_name: Name of the test
            
        Returns:
            Path to created directory
        """
        timestamp = TestHelper.get_datetime_string()
        dir_name = f"{test_name}_{timestamp}"
        test_dir = Path(base_path) / dir_name
        test_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Created test data directory: {test_dir}")
        return test_dir
    
    @staticmethod
    def cleanup_test_data_directory(directory: Path) -> None:
        """
        Clean up test data directory
        
        Args:
            directory: Directory to clean up
        """
        try:
            if directory.exists():
                import shutil
                shutil.rmtree(directory)
                logger.info(f"Cleaned up test data directory: {directory}")
        except Exception as e:
            logger.error(f"Failed to clean up directory {directory}: {e}")
    
    @staticmethod
    def measure_execution_time(func: Callable) -> tuple:
        """
        Measure execution time of a function
        
        Args:
            func: Function to measure
            
        Returns:
            Tuple of (result, execution_time_ms)
        """
        start_time = time.time()
        result = func()
        end_time = time.time()
        execution_time_ms = (end_time - start_time) * 1000
        
        return result, execution_time_ms
    
    @staticmethod
    def assert_with_retry(
        assertion_func: Callable,
        max_attempts: int = 3,
        delay: int = 1000
    ) -> None:
        """
        Assert with retry capability
        
        Args:
            assertion_func: Function that performs assertion
            max_attempts: Maximum number of attempts
            delay: Delay between attempts in milliseconds
        """
        for attempt in range(max_attempts):
            try:
                assertion_func()
                return
            except AssertionError as e:
                if attempt == max_attempts - 1:
                    raise
                logger.warning(f"Assertion failed on attempt {attempt + 1}: {e}")
                time.sleep(delay / 1000)


# Convenience functions
def wait_for_condition(condition: Callable[[], bool], timeout: int = 30000, poll_interval: int = 500) -> bool:
    """Wait for condition to be true"""
    return TestHelper.wait_for_condition(condition, timeout, poll_interval)


def generate_random_string(length: int = 10, include_numbers: bool = True) -> str:
    """Generate random string"""
    return TestHelper.generate_random_string(length, include_numbers)


def create_test_workspace(base_path: str, test_name: str) -> Path:
    """Create test workspace directory"""
    return TestHelper.create_test_data_directory(base_path, test_name)


def cleanup_test_workspace(directory: Path) -> None:
    """Clean up test workspace directory"""
    TestHelper.cleanup_test_data_directory(directory)


def retry_on_failure(func: Callable, max_attempts: int = 3, delay: int = 1000) -> Any:
    """Retry function on failure"""
    return TestHelper.retry_on_failure(func, max_attempts, delay)
