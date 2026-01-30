/**
 * Global setup for Playwright tests
 */

import { chromium, FullConfig } from '@playwright/test';
import path from 'path';

async function globalSetup(config: FullConfig) {
  console.log('🚀 Starting global setup for HarborPilot E2E tests');
  
  // Create necessary directories
  const fs = require('fs');
  const directories = [
    'reports',
    'reports/screenshots',
    'reports/playwright',
    'test-results',
    'fixtures/workspaces',
    'fixtures/responses'
  ];
  
  directories.forEach(dir => {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
      console.log(`📁 Created directory: ${dir}`);
    }
  });
  
  // Set up test environment variables
  process.env.HARBORPILOT_TEST_ENV = 'test';
  process.env.HARBORPILOT_TEST_BASE_URL = process.env.HARBORPILOT_TEST_BASE_URL || 'http://localhost:5173';
  process.env.HARBORPILOT_TEST_TIMEOUT = '30000';
  process.env.HARBORPILOT_TEST_RETRIES = '2';
  
  console.log('✅ Global setup completed');
}

export default globalSetup;
