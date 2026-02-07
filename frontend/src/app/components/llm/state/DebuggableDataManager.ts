/**
 * DebuggableDataManager
 * 
 * Phase 4.1: Debug Tools & Development Experience
 * - Comprehensive debugging capabilities
 * - Performance metrics
 * - Event history inspection
 * - State snapshots
 */

import { OptimisticDataManager } from './OptimisticDataManager';
import type { UnifiedLlmConfig } from '../types';

export interface PerformanceMetrics {
  renderTime: number;
  updateTime: number;
  cacheHitRate: number;
  totalOperations: number;
  averageOperationTime: number;
}

export interface DebugInfo {
  dataManagerState: {
    version: number;
    cacheSize: number;
    pendingUpdates: number;
    optimisticUpdates: number;
    loadingOperations: number;
  };
  viewStates: {
    list: {
      isLoaded: boolean;
      loadTime: number;
      error: string | null;
    };
    visual: {
      isLoaded: boolean;
      loadTime: number;
      error: string | null;
    };
    deepTest: {
      isLoaded: boolean;
      loadTime: number;
      error: string | null;
    };
  };
  recentEvents: Array<{
    type: string;
    entityId: string;
    timestamp: string;
  }>;
  performanceMetrics: PerformanceMetrics;
  cacheStats: {
    hits: number;
    misses: number;
    hitRate: number;
    size: number;
  };
  batchStats: {
    totalBatches: number;
    totalUpdates: number;
    avgBatchSize: number;
    pendingUpdates: number;
  };
  conflictStats: {
    totalConflicts: number;
    pendingUpdates: number;
    currentVersion: number;
  };
  optimisticStats: {
    pending: number;
    success: number;
    error: number;
    rollbackStackSize: number;
  };
  unifiedConfig: UnifiedLlmConfig;
}

export interface StateSnapshot {
  id: string;
  timestamp: string;
  description: string;
  state: UnifiedLlmConfig;
  metrics: Partial<PerformanceMetrics>;
}

export class DebuggableDataManager extends OptimisticDataManager {
  private debugMode = false;
  private performanceMetrics: PerformanceMetrics = {
    renderTime: 0,
    updateTime: 0,
    cacheHitRate: 0,
    totalOperations: 0,
    averageOperationTime: 0,
  };
  private operationTimes: number[] = [];
  private maxOperationHistory = 100;
  private snapshots: StateSnapshot[] = [];
  private maxSnapshots = 10;
  private operationStartTime = 0;

  /**
   * Enable debug mode
   */
  public enableDebugMode(): void {
    this.debugMode = true;
    this.setDebugMode(true);
    console.log('[DebuggableDataManager] Debug mode enabled');
    console.log('[DebuggableDataManager] Available commands:');
    console.log('  - getDebugInfo(): Get comprehensive debug information');
    console.log('  - takeSnapshot(desc): Save current state snapshot');
    console.log('  - restoreSnapshot(id): Restore to a saved snapshot');
    console.log('  - compareSnapshots(id1, id2): Compare two snapshots');
    console.log('  - getPerformanceMetrics(): Get performance statistics');
    console.log('  - clearPerformanceMetrics(): Reset performance tracking');
  }

  /**
   * Disable debug mode
   */
  public disableDebugMode(): void {
    this.debugMode = false;
    this.setDebugMode(false);
    console.log('[DebuggableDataManager] Debug mode disabled');
  }

  /**
   * Check if debug mode is enabled
   */
  public isDebugMode(): boolean {
    return this.debugMode;
  }

  /**
   * Get comprehensive debug information
   */
  public getDebugInfo(): DebugInfo {
    const cacheStats = this.getCacheStats();
    const batchStats = this.getBatchStats();
    const conflictStats = this.getConflictStats();
    const optimisticStats = this.getOptimisticStats();
    const eventHistory = this.getEventHistory();
    const lazyStats = this.getLazyStats();

    return {
      dataManagerState: {
        version: conflictStats.currentVersion,
        cacheSize: cacheStats.size,
        pendingUpdates: batchStats.pendingUpdates + conflictStats.pendingUpdates,
        optimisticUpdates: optimisticStats.pending,
        loadingOperations: this.getLoadingSummary().active,
      },
      viewStates: {
        list: {
          isLoaded: lazyStats.loadedViews.includes('list'),
          loadTime: this.getViewLoadTime('list'),
          error: this.getViewLoadError('list'),
        },
        visual: {
          isLoaded: lazyStats.loadedViews.includes('visual'),
          loadTime: this.getViewLoadTime('visual'),
          error: this.getViewLoadError('visual'),
        },
        deepTest: {
          isLoaded: lazyStats.loadedViews.includes('deepTest'),
          loadTime: this.getViewLoadTime('deepTest'),
          error: this.getViewLoadError('deepTest'),
        },
      },
      recentEvents: eventHistory.slice(-10).map((e) => ({
        type: e.type,
        entityId: e.entityId,
        timestamp: e.timestamp,
      })),
      performanceMetrics: { ...this.performanceMetrics },
      cacheStats: {
        hits: cacheStats.hits,
        misses: cacheStats.misses,
        hitRate: cacheStats.hitRate,
        size: cacheStats.size,
      },
      batchStats: {
        totalBatches: batchStats.totalBatches,
        totalUpdates: batchStats.totalUpdates,
        avgBatchSize: batchStats.avgBatchSize,
        pendingUpdates: batchStats.pendingUpdates,
      },
      conflictStats: {
        totalConflicts: conflictStats.totalConflicts,
        pendingUpdates: conflictStats.pendingUpdates,
        currentVersion: conflictStats.currentVersion,
      },
      optimisticStats: {
        pending: optimisticStats.pending,
        success: optimisticStats.success,
        error: optimisticStats.error,
        rollbackStackSize: optimisticStats.rollbackStackSize,
      },
      unifiedConfig: this.getUnifiedConfig(),
    };
  }

  /**
   * Override getViewData to track performance
   */
  public getViewData<T>(viewType: 'list' | 'visual' | 'deepTest'): T {
    const startTime = performance.now();
    
    const result = super.getViewData<T>(viewType);
    
    const endTime = performance.now();
    const duration = endTime - startTime;
    
    this.performanceMetrics.renderTime = duration;
    this.trackOperationTime(duration);
    
    if (this.debugMode) {
      console.log(`[Performance] getViewData('${viewType}'): ${duration.toFixed(2)}ms`);
    }
    
    return result;
  }

  /**
   * Track operation time
   */
  private trackOperationTime(duration: number): void {
    this.operationTimes.push(duration);
    
    if (this.operationTimes.length > this.maxOperationHistory) {
      this.operationTimes.shift();
    }
    
    this.performanceMetrics.totalOperations = this.operationTimes.length;
    this.performanceMetrics.averageOperationTime =
      this.operationTimes.reduce((a, b) => a + b, 0) / this.operationTimes.length;
  }

  /**
   * Start operation timing
   */
  protected startOperationTiming(): void {
    this.operationStartTime = performance.now();
  }

  /**
   * End operation timing
   */
  protected endOperationTiming(operationName: string): void {
    if (this.operationStartTime === 0) return;
    
    const duration = performance.now() - this.operationStartTime;
    this.performanceMetrics.updateTime = duration;
    this.trackOperationTime(duration);
    
    if (this.debugMode) {
      console.log(`[Performance] ${operationName}: ${duration.toFixed(2)}ms`);
    }
    
    this.operationStartTime = 0;
  }

  /**
   * Take a state snapshot
   */
  public takeSnapshot(description: string): StateSnapshot {
    const snapshot: StateSnapshot = {
      id: `snap_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date().toISOString(),
      description,
      state: JSON.parse(JSON.stringify(this.getUnifiedConfig())),
      metrics: { ...this.performanceMetrics },
    };
    
    this.snapshots.push(snapshot);
    
    if (this.snapshots.length > this.maxSnapshots) {
      this.snapshots.shift();
    }
    
    if (this.debugMode) {
      console.log(`[Snapshot] Created: ${snapshot.id} - ${description}`);
    }
    
    return snapshot;
  }

  /**
   * Get all snapshots
   */
  public getSnapshots(): StateSnapshot[] {
    return [...this.snapshots];
  }

  /**
   * Restore to a snapshot
   */
  public restoreSnapshot(snapshotId: string): boolean {
    const snapshot = this.snapshots.find((s) => s.id === snapshotId);
    if (!snapshot) {
      console.warn(`[Snapshot] Not found: ${snapshotId}`);
      return false;
    }
    
    // Restore state
    this.unifiedData = JSON.parse(JSON.stringify(snapshot.state));
    
    if (this.debugMode) {
      console.log(`[Snapshot] Restored: ${snapshotId} - ${snapshot.description}`);
    }
    
    return true;
  }

  /**
   * Compare two snapshots
   */
  public compareSnapshots(
    snapshotId1: string,
    snapshotId2: string
  ): { differences: string[]; added: string[]; removed: string[] } | null {
    const snap1 = this.snapshots.find((s) => s.id === snapshotId1);
    const snap2 = this.snapshots.find((s) => s.id === snapshotId2);
    
    if (!snap1 || !snap2) {
      console.warn('[Snapshot] One or both snapshots not found');
      return null;
    }
    
    const differences: string[] = [];
    const added: string[] = [];
    const removed: string[] = [];
    
    // Simple diff - can be expanded
    const keys1 = Object.keys(snap1.state);
    const keys2 = Object.keys(snap2.state);
    
    keys1.forEach((key) => {
      if (!(key in snap2.state)) {
        removed.push(key);
      } else if (JSON.stringify(snap1.state[key as keyof UnifiedLlmConfig]) !==
                 JSON.stringify(snap2.state[key as keyof UnifiedLlmConfig])) {
        differences.push(key);
      }
    });
    
    keys2.forEach((key) => {
      if (!(key in snap1.state)) {
        added.push(key);
      }
    });
    
    if (this.debugMode) {
      console.log(`[Snapshot] Comparison ${snapshotId1} vs ${snapshotId2}:`, {
        differences,
        added,
        removed,
      });
    }
    
    return { differences, added, removed };
  }

  /**
   * Delete a snapshot
   */
  public deleteSnapshot(snapshotId: string): boolean {
    const index = this.snapshots.findIndex((s) => s.id === snapshotId);
    if (index === -1) return false;
    
    this.snapshots.splice(index, 1);
    
    if (this.debugMode) {
      console.log(`[Snapshot] Deleted: ${snapshotId}`);
    }
    
    return true;
  }

  /**
   * Clear all snapshots
   */
  public clearSnapshots(): void {
    this.snapshots = [];
    
    if (this.debugMode) {
      console.log('[Snapshot] All snapshots cleared');
    }
  }

  /**
   * Get performance metrics
   */
  public getPerformanceMetrics(): PerformanceMetrics & {
    operationHistory: number[];
  } {
    return {
      ...this.performanceMetrics,
      operationHistory: [...this.operationTimes],
    };
  }

  /**
   * Clear performance metrics
   */
  public clearPerformanceMetrics(): void {
    this.performanceMetrics = {
      renderTime: 0,
      updateTime: 0,
      cacheHitRate: 0,
      totalOperations: 0,
      averageOperationTime: 0,
    };
    this.operationTimes = [];
    
    if (this.debugMode) {
      console.log('[Performance] Metrics cleared');
    }
  }

  /**
   * Log current state to console
   */
  public logState(): void {
    console.group('[DebuggableDataManager] Current State');
    console.log('Unified Config:', this.getUnifiedConfig());
    console.log('Debug Info:', this.getDebugInfo());
    console.groupEnd();
  }

  /**
   * Export state to JSON
   */
  public exportState(): string {
    return JSON.stringify(this.getUnifiedConfig(), null, 2);
  }

  /**
   * Import state from JSON
   */
  public importState(json: string): boolean {
    try {
      const state = JSON.parse(json) as UnifiedLlmConfig;
      this.unifiedData = state;
      
      if (this.debugMode) {
        console.log('[DebuggableDataManager] State imported');
      }
      
      return true;
    } catch (error) {
      console.error('[DebuggableDataManager] Failed to import state:', error);
      return false;
    }
  }

  /**
   * Monitor a specific value
   */
  public watch<T>(
    getter: () => T,
    name: string,
    interval: number = 1000
  ): () => void {
    let lastValue = getter();
    
    const check = () => {
      const currentValue = getter();
      if (JSON.stringify(currentValue) !== JSON.stringify(lastValue)) {
        if (this.debugMode) {
          console.log(`[Watch] ${name} changed:`, lastValue, '->', currentValue);
        }
        lastValue = currentValue;
      }
    };
    
    const intervalId = setInterval(check, interval);
    
    return () => clearInterval(intervalId);
  }

  /**
   * Get detailed cache information
   */
  public getDetailedCacheInfo(): Array<{
    key: string;
    age: number;
    accessCount: number;
    size: number;
    isExpired: boolean;
  }> {
    const cacheInfo = this.getCacheInfo();
    const now = Date.now();
    
    return cacheInfo.map((entry) => ({
      ...entry,
      isExpired: entry.age > 5000, // Default 5s TTL
    }));
  }

  /**
   * Cleanup
   */
  public destroy(): void {
    this.snapshots = [];
    this.operationTimes = [];
    super.destroy();
  }
}
