/**
 * Global teardown for Playwright tests
 */

import { FullConfig } from '@playwright/test';

async function globalTeardown(config: FullConfig) {
  console.log('🧹 Starting global teardown for HarborPilot E2E tests');
  
  // Clean up temporary files if needed
  const fs = require('fs');
  const path = require('path');
  
  // Clean up old test results (keep last 5 runs)
  const testResultsDir = 'test-results';
  if (fs.existsSync(testResultsDir)) {
    const files = fs.readdirSync(testResultsDir);
    if (files.length > 5) {
      // Sort files by creation time and remove oldest
      const filesWithStats = files.map(file => ({
        name: file,
        path: path.join(testResultsDir, file),
        stats: fs.statSync(path.join(testResultsDir, file))
      }));
      
      filesWithStats.sort((a, b) => a.stats.birthtimeMs - b.stats.birthtimeMs);
      
      // Remove oldest files
      const filesToRemove = filesWithStats.slice(0, files.length - 5);
      filesToRemove.forEach(file => {
        if (fs.statSync(file.path).isDirectory()) {
          fs.rmSync(file.path, { recursive: true, force: true });
        } else {
          fs.unlinkSync(file.path);
        }
        console.log(`🗑️  Removed old test result: ${file.name}`);
      });
    }
  }
  
  console.log('✅ Global teardown completed');
}

export default globalTeardown;
