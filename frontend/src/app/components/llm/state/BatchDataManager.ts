/**
 * BatchDataManager
 * 
 * Phase 1.2: Batch Update Optimization
 * - Microtask batching for updates within a frame
 * - Automatic coalescing of multiple updates
 * - Priority-based update queue
 */

import { OptimizedDataManager } from './OptimizedDataManager';
import type { UnifiedLlmConfig } from '../types';

interface QueuedUpdate {
  id: string;
  type: 'view' | 'unified';
  viewType?: 'list' | 'visual' | 'deepTest';
  data: any;
  priority: number;
  timestamp: number;
  resolve: (value: UnifiedLlmConfig) => void;
  reject: (reason: any) => void;
}

interface BatchStats {
  totalBatches: number;
  totalUpdates: number;
  avgBatchSize: number;
  maxBatchSize: number;
}

export class BatchDataManager extends OptimizedDataManager {
  private updateQueue: QueuedUpdate[] = [];
  private isProcessing = false;
  private batchTimeout: NodeJS.Timeout | null = null;
  private frameId: number | null = null;
  private batchDelay = 16; // One frame (60fps)
  private maxBatchSize = 100; // Maximum updates per batch
  private batchStats: BatchStats = {
    totalBatches: 0,
    totalUpdates: 0,
    avgBatchSize: 0,
    maxBatchSize: 0,
  };
  private debugMode = false;
  private updateIdCounter = 0;

  constructor(
    initialData: UnifiedLlmConfig,
    options?: {
      cacheTimeout?: number;
      maxCacheSize?: number;
      batchDelay?: number;
      maxBatchSize?: number;
      debugMode?: boolean;
    }
  ) {
    super(initialData, options);
    
    if (options?.batchDelay) {
      this.batchDelay = options.batchDelay;
    }
    if (options?.maxBatchSize) {
      this.maxBatchSize = options.maxBatchSize;
    }
    if (options?.debugMode) {
      this.debugMode = options.debugMode;
    }
  }

  /**
   * Queue an update to be processed in batch
   */
  private queueUpdate(
    type: 'view' | 'unified',
    data: any,
    priority: number = 0,
    viewType?: 'list' | 'visual' | 'deepTest'
  ): Promise<UnifiedLlmConfig> {
    return new Promise((resolve, reject) => {
      const update: QueuedUpdate = {
        id: `${Date.now()}_${++this.updateIdCounter}`,
        type,
        viewType,
        data,
        priority,
        timestamp: Date.now(),
        resolve,
        reject,
      };

      // Add to queue with priority sorting
      this.insertWithPriority(update);
      
      // Schedule batch processing
      this.scheduleBatch();
    });
  }

  /**
   * Insert update maintaining priority order
   */
  private insertWithPriority(update: QueuedUpdate): void {
    // Higher priority = processed first
    const insertIndex = this.updateQueue.findIndex(
      existing => existing.priority < update.priority
    );
    
    if (insertIndex === -1) {
      this.updateQueue.push(update);
    } else {
      this.updateQueue.splice(insertIndex, 0, update);
    }
  }

  /**
   * Schedule batch processing using requestAnimationFrame or setTimeout
   */
  private scheduleBatch(): void {
    if (this.isProcessing) return;

    // Cancel existing timeout
    if (this.batchTimeout) {
      clearTimeout(this.batchTimeout);
      this.batchTimeout = null;
    }

    // Cancel existing frame
    if (this.frameId !== null) {
      cancelAnimationFrame(this.frameId);
      this.frameId = null;
    }

    // Use requestAnimationFrame if available, fallback to setTimeout
    if (typeof window !== 'undefined' && window.requestAnimationFrame) {
      this.frameId = window.requestAnimationFrame(() => {
        this.frameId = null;
        this.processBatch();
      });
    } else {
      this.batchTimeout = setTimeout(() => {
        this.batchTimeout = null;
        this.processBatch();
      }, this.batchDelay);
    }
  }

  /**
   * Process all queued updates in a single batch
   */
  private async processBatch(): Promise<void> {
    if (this.isProcessing || this.updateQueue.length === 0) return;

    this.isProcessing = true;
    const batchStartTime = performance.now();
    const batchSize = Math.min(this.updateQueue.length, this.maxBatchSize);
    const currentBatch = this.updateQueue.splice(0, batchSize);

    // Coalesce updates - merge updates targeting the same view/data
    const coalescedUpdates = this.coalesceUpdates(currentBatch);

    if (this.debugMode) {
      console.log(`[Batch] Processing ${currentBatch.length} updates (${coalescedUpdates.length} coalesced)`);
    }

    try {
      // Group updates by type for efficient processing
      const viewUpdates = coalescedUpdates.filter(u => u.type === 'view');
      const unifiedUpdates = coalescedUpdates.filter(u => u.type === 'unified');

      // Process view updates first (they're more specific)
      for (const update of viewUpdates) {
        try {
          const result = update.viewType 
            ? super.updateViewData(update.viewType, update.data)
            : super.updateUnifiedData(update.data);
          update.resolve(result);
        } catch (error) {
          update.reject(error);
        }
      }

      // Process unified updates
      for (const update of unifiedUpdates) {
        try {
          const result = super.updateUnifiedData(update.data);
          update.resolve(result);
        } catch (error) {
          update.reject(error);
        }
      }

      // Update stats
      this.batchStats.totalBatches++;
      this.batchStats.totalUpdates += currentBatch.length;
      this.batchStats.avgBatchSize = this.batchStats.totalUpdates / this.batchStats.totalBatches;
      this.batchStats.maxBatchSize = Math.max(this.batchStats.maxBatchSize, currentBatch.length);

      if (this.debugMode) {
        const duration = performance.now() - batchStartTime;
        console.log(`[Batch] Completed in ${duration.toFixed(2)}ms`);
      }
    } catch (error) {
      // Reject all pending updates in this batch
      currentBatch.forEach(update => update.reject(error));
      console.error('[Batch] Error processing batch:', error);
    } finally {
      this.isProcessing = false;

      // Process remaining updates if any
      if (this.updateQueue.length > 0) {
        this.scheduleBatch();
      }
    }
  }

  /**
   * Coalesce updates to reduce redundant work
   * Merges multiple updates to the same target
   */
  private coalesceUpdates(updates: QueuedUpdate[]): QueuedUpdate[] {
    const coalesced = new Map<string, QueuedUpdate>();

    for (const update of updates) {
      const key = update.type === 'view' 
        ? `view_${update.viewType}` 
        : 'unified';

      const existing = coalesced.get(key);
      if (existing) {
        // Merge data - for objects, do a shallow merge
        if (typeof update.data === 'object' && typeof existing.data === 'object') {
          existing.data = { ...existing.data, ...update.data };
        } else {
          // For non-objects, later update wins
          existing.data = update.data;
        }
        // Keep higher priority
        existing.priority = Math.max(existing.priority, update.priority);
        
        // Resolve the newer promise with the result from the coalesced update
        update.resolve = existing.resolve;
      } else {
        coalesced.set(key, update);
      }
    }

    return Array.from(coalesced.values());
  }

  /**
   * Async update view data with batching
   * (Use this instead of updateViewData for batched updates)
   */
  public updateViewDataAsync<T>(
    viewType: 'list' | 'visual' | 'deepTest', 
    viewData: T,
    priority: number = 0
  ): Promise<UnifiedLlmConfig> {
    return this.queueUpdate('view', viewData, priority, viewType);
  }

  /**
   * Async update unified data with batching
   * (Use this instead of updateUnifiedData for batched updates)
   */
  public updateUnifiedDataAsync(
    updates: Partial<UnifiedLlmConfig>,
    priority: number = 0
  ): Promise<UnifiedLlmConfig> {
    return this.queueUpdate('unified', updates, priority);
  }

  /**
   * Synchronous update for urgent changes
   * Bypasses batching and applies immediately
   */
  public updateViewDataSync<T>(
    viewType: 'list' | 'visual' | 'deepTest', 
    viewData: T
  ): UnifiedLlmConfig {
    return super.updateViewData(viewType, viewData);
  }

  /**
   * Synchronous update for urgent changes
   */
  public updateUnifiedDataSync(updates: Partial<UnifiedLlmConfig>): UnifiedLlmConfig {
    return super.updateUnifiedData(updates);
  }

  /**
   * Flush all pending updates immediately
   */
  public async flush(): Promise<void> {
    if (this.updateQueue.length === 0) return;
    
    // Cancel scheduled batch
    if (this.batchTimeout) {
      clearTimeout(this.batchTimeout);
      this.batchTimeout = null;
    }
    if (this.frameId !== null) {
      cancelAnimationFrame(this.frameId);
      this.frameId = null;
    }

    // Process immediately
    await this.processBatch();
  }

  /**
   * Get batch processing statistics
   */
  public getBatchStats(): BatchStats & {
    pendingUpdates: number;
    isProcessing: boolean;
  } {
    return {
      totalBatches: this.batchStats.totalBatches,
      totalUpdates: this.batchStats.totalUpdates,
      avgBatchSize: this.batchStats.avgBatchSize,
      maxBatchSize: this.batchStats.maxBatchSize,
      pendingUpdates: this.updateQueue.length,
      isProcessing: this.isProcessing,
    };
  }

  /**
   * Get pending update count
   */
  public getPendingUpdateCount(): number {
    return this.updateQueue.length;
  }

  /**
   * Clear pending updates
   */
  public clearPendingUpdates(): void {
    // Reject all pending updates
    this.updateQueue.forEach(update => {
      update.reject(new Error('Update cancelled'));
    });
    this.updateQueue = [];
  }

  /**
   * Enable/disable debug mode
   */
  public setDebugMode(enabled: boolean): void {
    this.debugMode = enabled;
    super.setDebugMode(enabled);
  }

  /**
   * Cleanup resources
   */
  public destroy(): void {
    this.clearPendingUpdates();
    
    if (this.batchTimeout) {
      clearTimeout(this.batchTimeout);
      this.batchTimeout = null;
    }
    
    if (this.frameId !== null) {
      cancelAnimationFrame(this.frameId);
      this.frameId = null;
    }
  }
}
