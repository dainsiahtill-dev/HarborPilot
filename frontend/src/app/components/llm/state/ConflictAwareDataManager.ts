/**
 * ConflictAwareDataManager
 * 
 * Phase 2.2: Conflict Detection & Resolution
 * - Optimistic locking with versioning
 * - Automatic conflict detection
 * - Configurable resolution strategies
 */

import { ReactiveDataManager } from './ReactiveDataManager';
import type { UnifiedLlmConfig } from '../types';

export type ConflictResolutionStrategy = 'latest_wins' | 'merge' | 'manual' | 'reject';

export interface ConflictInfo {
  key: string;
  expectedVersion: number;
  actualVersion: number;
  localData: any;
  remoteData: any;
  timestamp: string;
}

export interface ConflictResolution {
  strategy: ConflictResolutionStrategy;
  resolvedData?: any;
  preserveLocal?: boolean;
}

export interface UpdateResult {
  success: boolean;
  data?: UnifiedLlmConfig;
  conflict?: ConflictInfo;
  resolution?: ConflictResolution;
  error?: string;
}

interface PendingUpdate {
  id: string;
  type: 'view' | 'unified';
  viewType?: 'list' | 'visual' | 'deepTest';
  data: any;
  expectedVersion: number;
  timestamp: number;
}

export class ConflictAwareDataManager extends ReactiveDataManager {
  private version = 0;
  private pendingUpdates = new Map<string, PendingUpdate>();
  private conflictHistory: ConflictInfo[] = [];
  private maxConflictHistory = 50;
  private defaultStrategy: ConflictResolutionStrategy = 'latest_wins';
  private onConflict?: (conflict: ConflictInfo) => Promise<ConflictResolution> | ConflictResolution;
  private debugMode = false;

  constructor(
    initialData: UnifiedLlmConfig,
    options?: {
      cacheTimeout?: number;
      maxCacheSize?: number;
      batchDelay?: number;
      maxBatchSize?: number;
      prefetchConfig?: any;
      enableHistory?: boolean;
      maxHistorySize?: number;
      defaultStrategy?: ConflictResolutionStrategy;
      onConflict?: (conflict: ConflictInfo) => Promise<ConflictResolution> | ConflictResolution;
      debugMode?: boolean;
    }
  ) {
    super(initialData, options);
    
    if (options?.defaultStrategy) {
      this.defaultStrategy = options.defaultStrategy;
    }
    if (options?.onConflict) {
      this.onConflict = options.onConflict;
    }
    if (options?.debugMode) {
      this.debugMode = options.debugMode;
    }
  }

  /**
   * Get current version
   */
  public getVersion(): number {
    return this.version;
  }

  /**
   * Update with conflict detection
   */
  public async updateViewDataWithConflict<T>(
    viewType: 'list' | 'visual' | 'deepTest',
    viewData: T,
    options?: {
      priority?: number;
      expectedVersion?: number;
      strategy?: ConflictResolutionStrategy;
    }
  ): Promise<UpdateResult> {
    const expectedVersion = options?.expectedVersion ?? this.version;
    const updateId = `${viewType}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    // Track pending update
    const pendingUpdate: PendingUpdate = {
      id: updateId,
      type: 'view',
      viewType,
      data: viewData,
      expectedVersion,
      timestamp: Date.now(),
    };
    this.pendingUpdates.set(updateId, pendingUpdate);

    try {
      // Check for conflicts
      const conflict = this.detectConflict(expectedVersion, updateId);

      if (conflict) {
        // Handle conflict
        const resolution = await this.resolveConflict(conflict, options?.strategy);

        if (resolution.strategy === 'reject') {
          return {
            success: false,
            conflict,
            resolution,
            error: 'Update rejected due to conflict',
          };
        }

        if (resolution.strategy === 'manual' && !resolution.resolvedData) {
          // Waiting for manual resolution
          return {
            success: false,
            conflict,
            resolution,
            error: 'Manual conflict resolution required',
          };
        }

        // Apply resolved data
        const resolvedData = resolution.resolvedData ?? viewData;
        const result = await super.updateViewData(viewType, resolvedData, options?.priority);
        this.version++;

        this.recordConflict(conflict);
        this.pendingUpdates.delete(updateId);

        return {
          success: true,
          data: result,
          conflict,
          resolution,
        };
      }

      // No conflict - apply update
      const result = await super.updateViewData(viewType, viewData, options?.priority);
      this.version++;
      this.pendingUpdates.delete(updateId);

      return {
        success: true,
        data: result,
      };
    } catch (error) {
      this.pendingUpdates.delete(updateId);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  /**
   * Unified data update with conflict detection
   */
  public async updateUnifiedDataWithConflict(
    updates: Partial<UnifiedLlmConfig>,
    options?: {
      priority?: number;
      expectedVersion?: number;
      strategy?: ConflictResolutionStrategy;
    }
  ): Promise<UpdateResult> {
    const expectedVersion = options?.expectedVersion ?? this.version;
    const updateId = `unified_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    const pendingUpdate: PendingUpdate = {
      id: updateId,
      type: 'unified',
      data: updates,
      expectedVersion,
      timestamp: Date.now(),
    };
    this.pendingUpdates.set(updateId, pendingUpdate);

    try {
      const conflict = this.detectConflict(expectedVersion, updateId);

      if (conflict) {
        const resolution = await this.resolveConflict(conflict, options?.strategy);

        if (resolution.strategy === 'reject') {
          return {
            success: false,
            conflict,
            resolution,
            error: 'Update rejected due to conflict',
          };
        }

        if (resolution.strategy === 'manual' && !resolution.resolvedData) {
          return {
            success: false,
            conflict,
            resolution,
            error: 'Manual conflict resolution required',
          };
        }

        const resolvedData = resolution.resolvedData ?? updates;
        const result = await super.updateUnifiedData(resolvedData, options?.priority);
        this.version++;

        this.recordConflict(conflict);
        this.pendingUpdates.delete(updateId);

        return {
          success: true,
          data: result,
          conflict,
          resolution,
        };
      }

      const result = await super.updateUnifiedData(updates, options?.priority);
      this.version++;
      this.pendingUpdates.delete(updateId);

      return {
        success: true,
        data: result,
      };
    } catch (error) {
      this.pendingUpdates.delete(updateId);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  /**
   * Detect conflicts
   */
  private detectConflict(expectedVersion: number, updateId: string): ConflictInfo | null {
    const actualVersion = this.version;

    if (actualVersion !== expectedVersion) {
      // Version mismatch - potential conflict
      const pendingUpdate = this.pendingUpdates.get(updateId);
      
      return {
        key: pendingUpdate?.viewType || 'unified',
        expectedVersion,
        actualVersion,
        localData: pendingUpdate?.data,
        remoteData: this.getUnifiedConfig(),
        timestamp: new Date().toISOString(),
      };
    }

    return null;
  }

  /**
   * Resolve conflicts
   */
  private async resolveConflict(
    conflict: ConflictInfo,
    strategy?: ConflictResolutionStrategy
  ): Promise<ConflictResolution> {
    const effectiveStrategy = strategy || this.defaultStrategy;

    // Call custom conflict handler if provided
    if (this.onConflict) {
      try {
        const customResolution = await this.onConflict(conflict);
        if (customResolution) {
          return customResolution;
        }
      } catch (error) {
        console.error('[ConflictAwareDataManager] Error in conflict handler:', error);
      }
    }

    // Apply default resolution strategy
    switch (effectiveStrategy) {
      case 'latest_wins':
        return {
          strategy: 'latest_wins',
          resolvedData: conflict.localData,
        };

      case 'merge':
        return {
          strategy: 'merge',
          resolvedData: this.mergeConflictData(conflict),
        };

      case 'manual':
        return {
          strategy: 'manual',
          // No resolved data - waiting for manual resolution
        };

      case 'reject':
        return {
          strategy: 'reject',
        };

      default:
        return {
          strategy: 'latest_wins',
          resolvedData: conflict.localData,
        };
    }
  }

  /**
   * Merge conflict data
   */
  private mergeConflictData(conflict: ConflictInfo): any {
    // Simple shallow merge - can be customized based on data structure
    if (typeof conflict.localData === 'object' && typeof conflict.remoteData === 'object') {
      return {
        ...conflict.remoteData,
        ...conflict.localData,
        // Preserve metadata from remote
        metadata: conflict.remoteData.metadata,
      };
    }
    return conflict.localData;
  }

  /**
   * Record conflict for history
   */
  private recordConflict(conflict: ConflictInfo): void {
    this.conflictHistory.push(conflict);
    if (this.conflictHistory.length > this.maxConflictHistory) {
      this.conflictHistory.shift();
    }

    if (this.debugMode) {
      console.warn('[ConflictAwareDataManager] Conflict recorded:', conflict);
    }
  }

  /**
   * Get conflict history
   */
  public getConflictHistory(): ConflictInfo[] {
    return [...this.conflictHistory];
  }

  /**
   * Clear conflict history
   */
  public clearConflictHistory(): void {
    this.conflictHistory = [];
  }

  /**
   * Get pending update count
   */
  public getPendingUpdateCount(): number {
    return this.pendingUpdates.size;
  }

  /**
   * Get pending updates
   */
  public getPendingUpdates(): PendingUpdate[] {
    return Array.from(this.pendingUpdates.values());
  }

  /**
   * Cancel a pending update
   */
  public cancelPendingUpdate(updateId: string): boolean {
    const deleted = this.pendingUpdates.delete(updateId);
    if (deleted && this.debugMode) {
      console.log(`[ConflictAwareDataManager] Cancelled update: ${updateId}`);
    }
    return deleted;
  }

  /**
   * Cancel all pending updates
   */
  public cancelAllPendingUpdates(): void {
    const count = this.pendingUpdates.size;
    this.pendingUpdates.clear();
    
    if (this.debugMode && count > 0) {
      console.log(`[ConflictAwareDataManager] Cancelled ${count} pending updates`);
    }
  }

  /**
   * Force version update (for external sync)
   */
  public bumpVersion(): void {
    this.version++;
    
    if (this.debugMode) {
      console.log(`[ConflictAwareDataManager] Version bumped to ${this.version}`);
    }
  }

  /**
   * Set version (for external sync initialization)
   */
  public setVersion(version: number): void {
    this.version = version;
  }

  /**
   * Set default conflict resolution strategy
   */
  public setDefaultStrategy(strategy: ConflictResolutionStrategy): void {
    this.defaultStrategy = strategy;
  }

  /**
   * Set conflict handler
   */
  public setConflictHandler(
    handler: (conflict: ConflictInfo) => Promise<ConflictResolution> | ConflictResolution
  ): void {
    this.onConflict = handler;
  }

  /**
   * Set debug mode
   */
  public setDebugMode(enabled: boolean): void {
    this.debugMode = enabled;
    super.setDebugMode(enabled);
  }

  /**
   * Get conflict statistics
   */
  public getConflictStats(): {
    totalConflicts: number;
    pendingUpdates: number;
    currentVersion: number;
    strategies: Record<ConflictResolutionStrategy, number>;
  } {
    const strategies: Record<string, number> = {
      latest_wins: 0,
      merge: 0,
      manual: 0,
      reject: 0,
    };

    // Count strategies from history (simplified)
    // In a real implementation, you'd track which strategy was used for each conflict

    return {
      totalConflicts: this.conflictHistory.length,
      pendingUpdates: this.pendingUpdates.size,
      currentVersion: this.version,
      strategies: strategies as Record<ConflictResolutionStrategy, number>,
    };
  }

  /**
   * Cleanup
   */
  public destroy(): void {
    this.cancelAllPendingUpdates();
    this.clearConflictHistory();
    super.destroy();
  }
}
