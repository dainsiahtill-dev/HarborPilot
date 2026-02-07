/**
 * Data Manager Options
 * 
 * Common options interface for all data manager classes
 * Ensures proper type compatibility across the inheritance chain
 */

import type { StateChangeEvent, ConflictResolution } from './index';

export interface PrefetchConfig {
  enabled: boolean;
  delay: number;
  priority: 'low' | 'normal' | 'high';
}

export interface DataManagerOptions {
  // Cache options (OptimizedDataManager)
  cacheTimeout?: number;
  maxCacheSize?: number;

  // Batch options (BatchDataManager)
  batchDelay?: number;
  maxBatchBatchSize?: number;

  // Lazy loading options (LazyDataManager)
  prefetchConfig?: Partial<PrefetchConfig>;

  // Reactive options (ReactiveDataManager)
  enableHistory?: boolean;
  maxHistorySize?: number;

  // Conflict resolution options (ConflictAwareDataManager)
  defaultStrategy?: 'latest_wins' | 'merge' | 'manual' | 'reject';
  onConflict?: (conflict: any) => Promise<{ strategy: string; resolvedData?: any }> | { strategy: string; resolvedData?: any };

  // Common
  debugMode?: boolean;
}

// Default options
export const defaultDataManagerOptions: Required<DataManagerOptions> = {
  cacheTimeout: 5000,
  maxCacheSize: 50,
  batchDelay: 16,
  maxBatchBatchSize: 100,
  prefetchConfig: {
    enabled: true,
    delay: 100,
    priority: 'low',
  },
  enableHistory: false,
  maxHistorySize: 100,
  defaultStrategy: 'latest_wins',
  onConflict: async (conflict) => ({ strategy: 'latest_wins' }),
  debugMode: false,
};

// Merge options with defaults
export function mergeOptions(options?: DataManagerOptions): Required<DataManagerOptions> {
  return {
    ...defaultDataManagerOptions,
    ...options,
    prefetchConfig: {
      ...defaultDataManagerOptions.prefetchConfig,
      ...options?.prefetchConfig,
    },
  };
}
