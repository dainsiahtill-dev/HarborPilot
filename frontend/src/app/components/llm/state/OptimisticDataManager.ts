/**
 * OptimisticDataManager
 * 
 * Phase 3.1 & 3.2: Optimistic Updates & Loading State Management
 * - Optimistic UI updates with rollback capability
 * - Comprehensive loading state tracking
 * - Error handling with automatic recovery
 */

import { ConflictAwareDataManager } from './ConflictAwareDataManager';
import type { UnifiedLlmConfig } from '../types';

export interface OptimisticUpdate<T = any> {
  id: string;
  type: 'view' | 'unified';
  viewType?: 'list' | 'visual' | 'deepTest';
  optimisticData: T;
  previousData: T;
  timestamp: number;
  status: 'pending' | 'success' | 'error';
  error?: string;
}

export interface LoadingState {
  isLoading: boolean;
  operation: string;
  progress: number;
  error: string | null;
  startTime: number;
  estimatedDuration?: number;
}

export interface OptimisticResult {
  success: boolean;
  data?: UnifiedLlmConfig;
  rolledBack?: boolean;
  error?: string;
}

export class OptimisticDataManager extends ConflictAwareDataManager {
  private optimisticUpdates = new Map<string, OptimisticUpdate>();
  private rollbackStack: Array<() => void> = [];
  private loadingStates = new Map<string, LoadingState>();
  private loadingSubscribers = new Map<string, Set<(state: LoadingState) => void>>();
  private defaultEstimatedDuration = 1000; // 1 second default
  private debugMode = false;

  /**
   * Perform optimistic update
   * 
   * 1. Apply changes immediately
   * 2. Save rollback point
   * 3. Execute async operation
   * 4. Commit or rollback based on result
   */
  public async optimisticUpdate<T>(
    type: 'view' | 'unified',
    data: T,
    asyncOperation: () => Promise<void>,
    options?: {
      viewType?: 'list' | 'visual' | 'deepTest';
      operationName?: string;
      onRollback?: () => void;
    }
  ): Promise<OptimisticResult> {
    const updateId = `opt_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const operationName = options?.operationName || 'update';

    // Save current state for rollback
    const previousState = JSON.parse(JSON.stringify(this.getUnifiedConfig()));
    
    // Create rollback function
    const rollback = () => {
      this.unifiedData = previousState;
      if (options?.onRollback) {
        options.onRollback();
      }
      if (this.debugMode) {
        console.log(`[Optimistic] Rolled back: ${operationName}`);
      }
    };

    // Track optimistic update
    const optimisticUpdate: OptimisticUpdate<T> = {
      id: updateId,
      type,
      viewType: options?.viewType,
      optimisticData: data,
      previousData: previousState as T,
      timestamp: Date.now(),
      status: 'pending',
    };
    this.optimisticUpdates.set(updateId, optimisticUpdate);

    // Apply optimistic update immediately
    try {
      if (type === 'view' && options?.viewType) {
        super.updateViewDataSync(options.viewType, data);
      } else {
        super.updateUnifiedDataSync(data as Partial<UnifiedLlmConfig>);
      }
      
      // Add to rollback stack
      this.rollbackStack.push(rollback);
      
      if (this.debugMode) {
        console.log(`[Optimistic] Applied: ${operationName}`);
      }
    } catch (error) {
      this.optimisticUpdates.delete(updateId);
      return {
        success: false,
        error: 'Failed to apply optimistic update',
      };
    }

    // Start loading state
    const loadingKey = `op_${updateId}`;
    this.setLoadingState(loadingKey, {
      isLoading: true,
      operation: operationName,
      progress: 50, // Optimistic progress
      error: null,
      startTime: Date.now(),
    });

    try {
      // Execute actual async operation
      await asyncOperation();
      
      // Success - commit the update
      optimisticUpdate.status = 'success';
      this.optimisticUpdates.delete(updateId);
      this.rollbackStack.pop(); // Remove rollback since we don't need it
      
      // Update loading state to complete
      this.setLoadingState(loadingKey, {
        isLoading: false,
        operation: operationName,
        progress: 100,
        error: null,
        startTime: Date.now(),
      });

      if (this.debugMode) {
        console.log(`[Optimistic] Committed: ${operationName}`);
      }

      return {
        success: true,
        data: this.getUnifiedConfig(),
      };
    } catch (error) {
      // Error - rollback to previous state
      optimisticUpdate.status = 'error';
      optimisticUpdate.error = error instanceof Error ? error.message : 'Unknown error';
      
      // Execute rollback
      rollback();
      this.rollbackStack.pop();
      this.optimisticUpdates.delete(updateId);

      // Update loading state with error
      this.setLoadingState(loadingKey, {
        isLoading: false,
        operation: operationName,
        progress: 0,
        error: optimisticUpdate.error,
        startTime: Date.now(),
      });

      if (this.debugMode) {
        console.log(`[Optimistic] Failed and rolled back: ${operationName}`);
      }

      return {
        success: false,
        rolledBack: true,
        error: optimisticUpdate.error,
      };
    }
  }

  /**
   * Manually rollback last optimistic update
   */
  public rollback(): boolean {
    const rollbackFn = this.rollbackStack.pop();
    if (rollbackFn) {
      rollbackFn();
      
      // Mark latest optimistic update as rolled back
      const latestUpdate = Array.from(this.optimisticUpdates.values())
        .sort((a, b) => b.timestamp - a.timestamp)[0];
      
      if (latestUpdate) {
        latestUpdate.status = 'error';
        latestUpdate.error = 'Manually rolled back';
        this.optimisticUpdates.delete(latestUpdate.id);
      }

      return true;
    }
    return false;
  }

  /**
   * Rollback all pending optimistic updates
   */
  public rollbackAll(): void {
    while (this.rollbackStack.length > 0) {
      this.rollback();
    }
  }

  /**
   * Get pending optimistic updates
   */
  public getPendingOptimisticUpdates(): OptimisticUpdate[] {
    return Array.from(this.optimisticUpdates.values())
      .filter((u) => u.status === 'pending');
  }

  /**
   * Check if has pending optimistic updates
   */
  public hasPendingOptimisticUpdates(): boolean {
    return this.getPendingOptimisticUpdates().length > 0;
  }

  /**
   * Set loading state
   */
  public setLoadingState(key: string, state: LoadingState): void {
    this.loadingStates.set(key, state);
    
    // Notify subscribers
    const subscribers = this.loadingSubscribers.get(key);
    if (subscribers) {
      subscribers.forEach((callback) => {
        try {
          callback(state);
        } catch (error) {
          console.error('[OptimisticDataManager] Error in loading subscriber:', error);
        }
      });
    }
  }

  /**
   * Get loading state
   */
  public getLoadingState(key: string): LoadingState {
    return (
      this.loadingStates.get(key) ?? {
        isLoading: false,
        operation: '',
        progress: 0,
        error: null,
        startTime: 0,
      }
    );
  }

  /**
   * Subscribe to loading state changes
   */
  public subscribeToLoadingState(
    key: string,
    callback: (state: LoadingState) => void
  ): () => void {
    if (!this.loadingSubscribers.has(key)) {
      this.loadingSubscribers.set(key, new Set());
    }
    
    this.loadingSubscribers.get(key)!.add(callback);
    
    // Immediately call with current state
    callback(this.getLoadingState(key));
    
    return () => {
      this.loadingSubscribers.get(key)?.delete(callback);
    };
  }

  /**
   * Update loading progress
   */
  public updateLoadingProgress(key: string, progress: number): void {
    const state = this.loadingStates.get(key);
    if (state) {
      state.progress = Math.min(100, Math.max(0, progress));
      this.setLoadingState(key, state);
    }
  }

  /**
   * Start loading operation
   */
  public startLoading(
    key: string,
    operation: string,
    estimatedDuration?: number
  ): void {
    this.setLoadingState(key, {
      isLoading: true,
      operation,
      progress: 0,
      error: null,
      startTime: Date.now(),
      estimatedDuration: estimatedDuration || this.defaultEstimatedDuration,
    });

    // Auto-update progress if estimated duration is provided
    if (estimatedDuration) {
      this.simulateProgress(key, estimatedDuration);
    }
  }

  /**
   * End loading operation
   */
  public endLoading(key: string, error?: string): void {
    const state = this.loadingStates.get(key);
    if (state) {
      state.isLoading = false;
      state.progress = error ? 0 : 100;
      state.error = error || null;
      this.setLoadingState(key, state);
    }
  }

  /**
   * Simulate progress updates
   */
  private simulateProgress(key: string, duration: number): void {
    const startTime = Date.now();
    const updateInterval = 100; // Update every 100ms
    
    const updateProgress = () => {
      const state = this.loadingStates.get(key);
      if (!state || !state.isLoading) return;
      
      const elapsed = Date.now() - startTime;
      const progress = Math.min(90, (elapsed / duration) * 100); // Cap at 90% until complete
      
      this.updateLoadingProgress(key, progress);
      
      if (progress < 90) {
        setTimeout(updateProgress, updateInterval);
      }
    };
    
    setTimeout(updateProgress, updateInterval);
  }

  /**
   * Get all loading states
   */
  public getAllLoadingStates(): Record<string, LoadingState> {
    const result: Record<string, LoadingState> = {};
    this.loadingStates.forEach((state, key) => {
      result[key] = state;
    });
    return result;
  }

  /**
   * Check if any loading is active
   */
  public isAnyLoading(): boolean {
    return Array.from(this.loadingStates.values()).some((s) => s.isLoading);
  }

  /**
   * Get loading summary
   */
  public getLoadingSummary(): {
    total: number;
    active: number;
    errors: number;
    operations: string[];
  } {
    const states = Array.from(this.loadingStates.values());
    return {
      total: states.length,
      active: states.filter((s) => s.isLoading).length,
      errors: states.filter((s) => s.error).length,
      operations: states.filter((s) => s.isLoading).map((s) => s.operation),
    };
  }

  /**
   * Clear loading state
   */
  public clearLoadingState(key: string): void {
    this.loadingStates.delete(key);
  }

  /**
   * Clear all loading states
   */
  public clearAllLoadingStates(): void {
    this.loadingStates.clear();
  }

  /**
   * Get optimistic update statistics
   */
  public getOptimisticStats(): {
    pending: number;
    success: number;
    error: number;
    total: number;
    rollbackStackSize: number;
  } {
    const updates = Array.from(this.optimisticUpdates.values());
    return {
      pending: updates.filter((u) => u.status === 'pending').length,
      success: updates.filter((u) => u.status === 'success').length,
      error: updates.filter((u) => u.status === 'error').length,
      total: updates.length,
      rollbackStackSize: this.rollbackStack.length,
    };
  }

  /**
   * Set debug mode
   */
  public setDebugMode(enabled: boolean): void {
    this.debugMode = enabled;
    super.setDebugMode(enabled);
  }

  /**
   * Cleanup
   */
  public destroy(): void {
    // Rollback all pending optimistic updates
    this.rollbackAll();
    
    this.optimisticUpdates.clear();
    this.loadingStates.clear();
    this.loadingSubscribers.clear();
    
    super.destroy();
  }
}
