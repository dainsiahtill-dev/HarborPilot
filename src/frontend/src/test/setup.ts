/**
 * Vitest 测试环境设置
 */

import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// 每次测试后自动清理
afterEach(() => {
    cleanup();
});
