/**
 * LazyDataManager
 * 
 * Phase 1.3: Lazy Loading Implementation
 * - Async data loading with promises
 * - View-level lazy initialization
 * - Loading state management
 * - Prefetching support
 */

import { BatchDataManager } from './BatchDataManager';
import type { UnifiedLlmConfig } from '../types';

interface LoadingState {
  isLoading: boolean;
  error: string | null;
  progress: number;
  startTime: number;
}

interface ViewLoadState {
  isLoaded: boolean;
  isLoading: boolean;
  promise: Promise<any> | null;
  error: string | null;
  loadTime: number;
}

interface PrefetchConfig {
  enabled: boolean;
  delay: number;
  priority: 'low' | 'normal' | 'high';
}

export class LazyDataManager extends BatchDataManager {
  private viewLoadStates = new Map<string, ViewLoadState>();
  private loadingStates = new Map<string, LoadingState>();
  private prefetchQueue: string[] = [];
  private prefetchTimeout: NodeJS.Timeout | null = null;
  private defaultPrefetchConfig: PrefetchConfig = {
    enabled: true,
    delay: 100,
    priority: 'low',
  };
  private debugMode = false;

  constructor(
    initialData: UnifiedLlmConfig,
    options?: {
      cacheTimeout?: number;
      maxCacheSize?: number;
      batchDelay?: number;
      maxBatchSize?: number;
      prefetchConfig?: Partial<PrefetchConfig>;
      debugMode?: boolean;
    }
  ) {
    super(initialData, options);
    
    if (options?.prefetchConfig) {
      this.defaultPrefetchConfig = { ...this.defaultPrefetchConfig, ...options.prefetchConfig };
    }
    if (options?.debugMode) {
      this.debugMode = options.debugMode;
    }

    // Initialize view load states
    this.viewLoadStates.set('list', this.createInitialViewLoadState());
    this.viewLoadStates.set('visual', this.createInitialViewLoadState());
    this.viewLoadStates.set('deepTest', this.createInitialViewLoadState());
  }

  private createInitialViewLoadState(): ViewLoadState {
    return {
      isLoaded: false,
      isLoading: false,
      promise: null,
      error: null,
      loadTime: 0,
    };
  }

  /**
   * Async data loading with loading state management
   */
  public async getViewDataAsync<T>(
    viewType: 'list' | 'visual' | 'deepTest',
    options?: {
      forceReload?: boolean;
      timeout?: number;
    }
  ): Promise<{ data: T; loadingState: LoadingState }> {
    const viewState = this.viewLoadStates.get(viewType)!;
    const loadingKey = `view_${viewType}`;

    // Check if already loaded and not forcing reload
    if (viewState.isLoaded && !options?.forceReload) {
      return {
        data: super.getViewData<T>(viewType),
        loadingState: this.getLoadingState(loadingKey),
      };
    }

    // Check if already loading
    if (viewState.isLoading && viewState.promise) {
      return viewState.promise;
    }

    // Start new load
    const loadPromise = this.loadViewDataAsync<T>(viewType, options?.timeout);
    
    viewState.isLoading = true;
    viewState.promise = loadPromise;
    viewState.error = null;

    this.setLoadingState(loadingKey, {
      isLoading: true,
      error: null,
      progress: 0,
      startTime: Date.now(),
    });

    try {
      const result = await loadPromise;
      
      // Update view state
      viewState.isLoaded = true;
      viewState.isLoading = false;
      viewState.promise = null;
      viewState.loadTime = Date.now() - result.loadingState.startTime;
      
      this.setLoadingState(loadingKey, {
        isLoading: false,
        error: null,
        progress: 100,
        startTime: result.loadingState.startTime,
      });

      if (this.debugMode) {
        console.log(`[Lazy Load] ${viewType} loaded in ${viewState.loadTime}ms`);
      }

      return result;
    } catch (error) {
      // Update error state
      viewState.isLoading = false;
      viewState.promise = null;
      viewState.error = error instanceof Error ? error.message : 'Unknown error';
      
      this.setLoadingState(loadingKey, {
        isLoading: false,
        error: viewState.error,
        progress: 0,
        startTime: Date.now(),
      });

      throw error;
    }
  }

  /**
   * Load view data asynchronously
   */
  private async loadViewDataAsync<T>(
    viewType: 'list' | 'visual' | 'deepTest',
    timeout?: number
  ): Promise<{ data: T; loadingState: LoadingState }> {
    const loadingKey = `view_${viewType}`;
    const startTime = Date.now();

    try {
      // Simulate async work (e.g., Web Worker, large data processing)
      // In production, this could be:
      // - Web Worker computation
      // - Chunked data loading
      // - Complex data transformation
      
      await this.simulateAsyncWork(10); // Small delay for async boundary

      // Update progress
      this.updateLoadingProgress(loadingKey, 50);

      // Get the data
      const data = super.getViewData<T>(viewType);

      // More async work if needed
      await this.simulateAsyncWork(5);

      this.updateLoadingProgress(loadingKey, 100);

      return {
        data,
        loadingState: {
          isLoading: false,
          error: null,
          progress: 100,
          startTime,
        },
      };
    } catch (error) {
      throw error;
    }
  }

  /**
   * Simulate async work (can be replaced with real async operations)
   */
  private simulateAsyncWork(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Check if a view is loaded
   */
  public isViewLoaded(viewType: 'list' | 'visual' | 'deepTest'): boolean {
    return this.viewLoadStates.get(viewType)?.isLoaded ?? false;
  }

  /**
   * Check if a view is currently loading
   */
  public isViewLoading(viewType: 'list' | 'visual' | 'deepTest'): boolean {
    return this.viewLoadStates.get(viewType)?.isLoading ?? false;
  }

  /**
   * Get view load error if any
   */
  public getViewLoadError(viewType: 'list' | 'visual' | 'deepTest'): string | null {
    return this.viewLoadStates.get(viewType)?.error ?? null;
  }

  /**
   * Get view load time
   */
  public getViewLoadTime(viewType: 'list' | 'visual' | 'deepTest'): number {
    return this.viewLoadStates.get(viewType)?.loadTime ?? 0;
  }

  /**
   * Prefetch view data for anticipated usage
   */
  public prefetchView(
    viewType: 'list' | 'visual' | 'deepTest',
    config?: Partial<PrefetchConfig>
  ): void {
    const prefetchConfig = { ...this.defaultPrefetchConfig, ...config };
    
    if (!prefetchConfig.enabled) return;
    if (this.isViewLoaded(viewType) || this.isViewLoading(viewType)) return;

    // Add to prefetch queue
    if (!this.prefetchQueue.includes(viewType)) {
      this.prefetchQueue.push(viewType);
    }

    // Schedule prefetch
    if (this.prefetchTimeout) {
      clearTimeout(this.prefetchTimeout);
    }

    this.prefetchTimeout = setTimeout(() => {
      this.processPrefetchQueue(prefetchConfig.priority);
    }, prefetchConfig.delay);
  }

  /**
   * Process prefetch queue
   */
  private async processPrefetchQueue(priority: string): Promise<void> {
    if (this.prefetchQueue.length === 0) return;

    if (this.debugMode) {
      console.log(`[Prefetch] Processing queue: ${this.prefetchQueue.join(', ')}`);
    }

    // Process queue based on priority
    const queue = [...this.prefetchQueue];
    this.prefetchQueue = [];

    for (const viewType of queue) {
      try {
        await this.getViewDataAsync(viewType as 'list' | 'visual' | 'deepTest');
        
        if (this.debugMode) {
          console.log(`[Prefetch] ${viewType} loaded`);
        }
      } catch (error) {
        console.warn(`[Prefetch] Failed to load ${viewType}:`, error);
      }

      // For low priority, yield between loads
      if (priority === 'low') {
        await this.simulateAsyncWork(0);
      }
    }
  }

  /**
   * Set loading state for a key
   */
  private setLoadingState(key: string, state: LoadingState): void {
    this.loadingStates.set(key, state);
  }

  /**
   * Get loading state for a key
   */
  public getLoadingState(key: string): LoadingState {
    return (
      this.loadingStates.get(key) ?? {
        isLoading: false,
        error: null,
        progress: 0,
        startTime: 0,
      }
    );
  }

  /**
   * Update loading progress
   */
  private updateLoadingProgress(key: string, progress: number): void {
    const state = this.loadingStates.get(key);
    if (state) {
      state.progress = progress;
    }
  }

  /**
   * Subscribe to loading state changes
   */
  public subscribeToLoadingState(
    key: string,
    callback: (state: LoadingState) => void
  ): () => void {
    let lastState = this.getLoadingState(key);

    const checkInterval = setInterval(() => {
      const currentState = this.getLoadingState(key);
      if (JSON.stringify(currentState) !== JSON.stringify(lastState)) {
        lastState = currentState;
        callback(currentState);
      }
    }, 16); // Check every frame

    return () => clearInterval(checkInterval);
  }

  /**
   * Reload a view (force refresh)
   */
  public async reloadView<T>(
    viewType: 'list' | 'visual' | 'deepTest'
  ): Promise<{ data: T; loadingState: LoadingState }> {
    // Reset view state
    const viewState = this.viewLoadStates.get(viewType)!;
    viewState.isLoaded = false;
    viewState.isLoading = false;
    viewState.promise = null;
    viewState.error = null;
    viewState.loadTime = 0;

    // Clear cache for this view
    this.invalidateViewCache(viewType);

    // Reload
    return this.getViewDataAsync<T>(viewType, { forceReload: true });
  }

  /**
   * Preload all views
   */
  public async preloadAllViews(): Promise<void> {
    const views: Array<'list' | 'visual' | 'deepTest'> = ['list', 'visual', 'deepTest'];
    
    await Promise.all(
      views.map(view => 
        this.getViewDataAsync(view).catch(err => {
          console.warn(`[Preload] Failed to load ${view}:`, err);
        })
      )
    );
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
   * Get lazy loading statistics
   */
  public getLazyStats(): {
    loadedViews: string[];
    loadingViews: string[];
    failedViews: string[];
    averageLoadTime: number;
  } {
    const loadedViews: string[] = [];
    const loadingViews: string[] = [];
    const failedViews: string[] = [];
    let totalLoadTime = 0;
    let loadedCount = 0;

    this.viewLoadStates.forEach((state, viewType) => {
      if (state.isLoaded) {
        loadedViews.push(viewType);
        totalLoadTime += state.loadTime;
        loadedCount++;
      } else if (state.isLoading) {
        loadingViews.push(viewType);
      } else if (state.error) {
        failedViews.push(viewType);
      }
    });

    return {
      loadedViews,
      loadingViews,
      failedViews,
      averageLoadTime: loadedCount > 0 ? totalLoadTime / loadedCount : 0,
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
   * Cleanup resources
   */
  public destroy(): void {
    if (this.prefetchTimeout) {
      clearTimeout(this.prefetchTimeout);
      this.prefetchTimeout = null;
    }
    
    this.loadingStates.clear();
    this.viewLoadStates.clear();
    this.prefetchQueue = [];
    
    super.destroy();
  }
}
