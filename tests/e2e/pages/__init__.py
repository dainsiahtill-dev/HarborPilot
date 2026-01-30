"""
Page Object Model for HarborPilot E2E tests
"""

from .base_page import BasePage
from .dashboard_page import DashboardPage
from .workspace_page import WorkspacePage

__all__ = ['BasePage', 'DashboardPage', 'WorkspacePage']
