import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for HarborPilot E2E tests
 */
export default defineConfig({
  testDir: './tests',
  
  // Global settings
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  
  // Reporter configuration
  reporter: [
    ['html', { outputFolder: 'reports/playwright' }],
    ['json', { outputFile: 'reports/playwright/results.json' }],
    ['junit', { outputFile: 'reports/playwright/junit.xml' }],
    ['list'],
  ],
  
  // Global timeout
  timeout: 30 * 1000,
  expect: {
    timeout: 10 * 1000,
  },
  
  // Test artifacts
  use: {
    // Base URL for tests
    baseURL: process.env.HARBORPILOT_TEST_BASE_URL || 'http://localhost:5173',
    
    // Browser settings
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    
    // Viewport and device
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,
    
    // Network settings
    bypassCSP: true,
    
    // Locale and timezone
    locale: 'en-US',
    timezoneId: 'America/New_York',
  },
  
  // Projects for different browsers
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    
    // Mobile browsers
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 12'] },
    },
  ],
  
  // Development server
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
  
  // Global setup and teardown
  globalSetup: require.resolve('./utils/global-setup.ts'),
  globalTeardown: require.resolve('./utils/global-teardown.ts'),
  
  // Output directory
  outputDir: 'test-results/',
  
  // Metadata
  metadata: {
    'Test Environment': process.env.NODE_ENV || 'test',
    'Test Suite': 'HarborPilot E2E',
  },
});
