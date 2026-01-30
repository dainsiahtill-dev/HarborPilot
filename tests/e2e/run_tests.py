#!/usr/bin/env python3
"""
Test runner script for HarborPilot E2E tests
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, cwd=None):
    """Run command and return result"""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    
    return result.returncode == 0


def install_dependencies():
    """Install test dependencies"""
    print("📦 Installing dependencies...")
    
    # Install Python dependencies
    if not run_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]):
        print("❌ Failed to install Python dependencies")
        return False
    
    # Install Playwright browsers
    if not run_command([sys.executable, "-m", "playwright", "install"]):
        print("❌ Failed to install Playwright browsers")
        return False
    
    print("✅ Dependencies installed successfully")
    return True


def setup_environment():
    """Set up test environment"""
    print("🔧 Setting up test environment...")
    
    # Create necessary directories
    directories = [
        "reports",
        "reports/screenshots",
        "reports/playwright",
        "test-results",
        "fixtures/workspaces",
        "fixtures/responses"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    # Set environment variables
    os.environ["HARBORPILOT_TEST_ENV"] = "test"
    os.environ["HARBORPILOT_TEST_BASE_URL"] = os.getenv(
        "HARBORPILOT_TEST_BASE_URL", "http://localhost:5173"
    )
    os.environ["HARBORPILOT_TEST_TIMEOUT"] = "30000"
    os.environ["HARBORPILOT_TEST_RETRIES"] = "2"
    
    print("✅ Environment setup completed")
    return True


def run_tests(test_type="all", headed=False, browser="chromium", verbose=False):
    """Run E2E tests"""
    print(f"🧪 Running {test_type} tests...")
    
    # Build pytest command
    cmd = [sys.executable, "-m", "pytest"]
    
    # Add test files based on type
    if test_type == "smoke":
        cmd.extend(["-m", "smoke"])
    elif test_type == "dashboard":
        cmd.extend(["-m", "dashboard"])
    elif test_type == "workflow":
        cmd.extend(["-m", "workflow"])
    elif test_type == "integration":
        cmd.extend(["-m", "integration"])
    elif test_type == "all":
        cmd.append("tests/")
    
    # Add options
    if verbose:
        cmd.append("-v")
    
    if headed:
        cmd.extend(["--headed"])
    
    if browser != "chromium":
        cmd.extend(["--browser", browser])
    
    # Add reporting
    cmd.extend([
        "--html=reports/report.html",
        "--self-contained-html",
        "--tb=short"
    ])
    
    # Run tests
    success = run_command(cmd)
    
    if success:
        print("✅ Tests completed successfully")
        print(f"📊 Report available at: reports/report.html")
    else:
        print("❌ Tests failed")
    
    return success


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="HarborPilot E2E Test Runner")
    
    parser.add_argument(
        "command",
        choices=["install", "setup", "test", "all"],
        help="Command to run"
    )
    
    parser.add_argument(
        "--type",
        choices=["all", "smoke", "dashboard", "workflow", "integration"],
        default="all",
        help="Type of tests to run"
    )
    
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run tests with headed browser"
    )
    
    parser.add_argument(
        "--browser",
        choices=["chromium", "firefox", "webkit"],
        default="chromium",
        help="Browser to use for tests"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # Change to E2E test directory
    e2e_dir = Path(__file__).parent
    os.chdir(e2e_dir)
    
    success = True
    
    if args.command in ["install", "all"]:
        success &= install_dependencies()
    
    if args.command in ["setup", "all"]:
        success &= setup_environment()
    
    if args.command in ["test", "all"]:
        success &= run_tests(
            test_type=args.type,
            headed=args.headed,
            browser=args.browser,
            verbose=args.verbose
        )
    
    if success:
        print("\n🎉 All operations completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Some operations failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
