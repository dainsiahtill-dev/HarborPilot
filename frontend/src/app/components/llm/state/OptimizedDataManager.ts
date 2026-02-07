/**
 * OptimizedDataManager
 * 
 * Phase 1.1: Cache Layer Enhancement
 * - Intelligent caching mechanism with TTL
 * - Hash-based change detection
 * - Automatic cache cleanup
 */

import { UnifiedLlmDataManager } from './UnifiedLlmDataManager';
import type { UnifiedLlmConfig } from '../types';

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  hash: string;
  accessCount: number;
}

export interface CacheStats {
  hits: number;
  misses: number;
  evictions: number;
  size: number;
}

export class OptimizedDataManager extends UnifiedLlmDataManager {
  private cache = new Map<string, CacheEntry<any>>();
  private cacheTimeout = 5000; // 5 seconds default TTL
  private maxCacheSize = 50; // Maximum number of cached entries
  private stats: CacheStats = {
    hits: 0,
    misses: 0,
    evictions: 0,
    size: 0,
  };
  private debugMode = false;

  constructor(
    initialData: UnifiedLlmConfig,
    options?: {
      cacheTimeout?: number;
      maxCacheSize?: number;
      debugMode?: boolean;
    }
  ) {
    super(initialData);
    
    if (options?.cacheTimeout) {
      this.cacheTimeout = options.cacheTimeout;
    }
    if (options?.maxCacheSize) {
      this.maxCacheSize = options.maxCacheSize;
    }
    if (options?.debugMode) {
      this.debugMode = options.debugMode;
    }
  }

  /**
   * Generate a fast hash for change detection
   * Uses provider count, role count, and timestamp instead of full JSON stringify
   */
  private getDataHash(): string {
    const unifiedData = this.getUnifiedConfig();
    const providers = Object.keys(unifiedData.providers || {}).length;
    const roles = Object.keys(unifiedData.roles || {}).length;
    const timestamp = unifiedData.metadata?.updated_at || Date.now();
    const version = unifiedData.metadata?.version || '1.0.0';
    
    return `${providers}-${roles}-${timestamp}-${version}`;
  }

  /**
   * Generate cache key for a view type
   */
  private getCacheKey(viewType: string, hash: string): string {
    return `${viewType}_${hash}`;
  }

  /**
   * Get view data with intelligent caching
   */
  public getViewData<T>(viewType: 'list' | 'visual' | 'deepTest'): T {
    const currentHash = this.getDataHash();
    const cacheKey = this.getCacheKey(viewType, currentHash);
    const now = Date.now();

    // Check cache
    const cached = this.cache.get(cacheKey);
    if (cached) {
      const isExpired = now - cached.timestamp > this.cacheTimeout;
      
      if (!isExpired) {
        // Cache hit - update access count for LRU
        cached.accessCount++;
        this.stats.hits++;
        
        if (this.debugMode) {
          console.log(`[Cache Hit] ${viewType} (age: ${now - cached.timestamp}ms)`);
        }
        
        return cached.data;
      }
      
      // Cache expired - will be replaced
      this.cache.delete(cacheKey);
    }

    // Cache miss - compute and cache
    this.stats.misses++;
    
    if (this.debugMode) {
      console.log(`[Cache Miss] ${viewType}`);
    }

    const data = super.getViewData<T>(viewType);
    
    // Check cache size before adding
    if (this.cache.size >= this.maxCacheSize) {
      this.evictLRU();
    }
    
    this.cache.set(cacheKey, {
      data,
      timestamp: now,
      hash: currentHash,
      accessCount: 1,
    });
    
    this.stats.size = this.cache.size;
    
    // Clean expired entries periodically (every 10 additions)
    if (this.cache.size % 10 === 0) {
      this.cleanExpiredCache();
    }
    
    return data;
  }

  /**
   * Evict least recently used entry
   */
  private evictLRU(): void {
    let lruKey: string | null = null;
    let minAccessCount = Infinity;
    let oldestTimestamp = Infinity;

    for (const [key, entry] of this.cache.entries()) {
      // Prioritize by access count, then by timestamp
      if (entry.accessCount < minAccessCount || 
          (entry.accessCount === minAccessCount && entry.timestamp < oldestTimestamp)) {
        minAccessCount = entry.accessCount;
        oldestTimestamp = entry.timestamp;
        lruKey = key;
      }
    }

    if (lruKey) {
      this.cache.delete(lruKey);
      this.stats.evictions++;
      
      if (this.debugMode) {
        console.log(`[Cache Eviction] ${lruKey}`);
      }
    }
  }

  /**
   * Clean expired cache entries
   */
  private cleanExpiredCache(): number {
    const now = Date.now();
    let cleaned = 0;

    for (const [key, entry] of this.cache.entries()) {
      if (now - entry.timestamp > this.cacheTimeout) {
        this.cache.delete(key);
        cleaned++;
      }
    }

    if (this.debugMode && cleaned > 0) {
      console.log(`[Cache Cleanup] Removed ${cleaned} expired entries`);
    }

    this.stats.size = this.cache.size;
    return cleaned;
  }

  /**
   * Override updateViewData to invalidate relevant caches
   */
  public updateViewData<T>(viewType: 'list' | 'visual' | 'deepTest', viewData: T): UnifiedLlmConfig {
    // Clear cache for this view type before update
    this.invalidateViewCache(viewType);
    
    return super.updateViewData(viewType, viewData);
  }

  /**
   * Override updateUnifiedData to clear all caches
   */
  public updateUnifiedData(updates: Partial<UnifiedLlmConfig>): UnifiedLlmConfig {
    // Clear all caches on unified data update
    this.clearCache();
    
    return super.updateUnifiedData(updates);
  }

  /**
   * Invalidate cache for a specific view type
   */
  public invalidateViewCache(viewType: string): void {
    const prefix = `${viewType}_`;
    for (const key of this.cache.keys()) {
      if (key.startsWith(prefix)) {
        this.cache.delete(key);
      }
    }
    
    if (this.debugMode) {
      console.log(`[Cache Invalidation] Cleared cache for ${viewType}`);
    }
    
    this.stats.size = this.cache.size;
  }

  /**
   * Clear all caches
   */
  public clearCache(): void {
    this.cache.clear();
    this.stats.size = 0;
    
    if (this.debugMode) {
      console.log('[Cache Clear] All caches cleared');
    }
  }

  /**
   * Get cache statistics
   */
  public getCacheStats(): CacheStats & {
    hitRate: number;
    avgAccessCount: number;
    oldestEntry: number;
  } {
    const total = this.stats.hits + this.stats.misses;
    const hitRate = total > 0 ? (this.stats.hits / total) * 100 : 0;
    
    let totalAccessCount = 0;
    let oldestTimestamp = Date.now();
    
    for (const entry of this.cache.values()) {
      totalAccessCount += entry.accessCount;
      if (entry.timestamp < oldestTimestamp) {
        oldestTimestamp = entry.timestamp;
      }
    }
    
    const avgAccessCount = this.cache.size > 0 ? totalAccessCount / this.cache.size : 0;
    
    return {
      ...this.stats,
      hitRate: Math.round(hitRate * 100) / 100,
      avgAccessCount: Math.round(avgAccessCount * 100) / 100,
      oldestEntry: Date.now() - oldestTimestamp,
    };
  }

  /**
   * Enable/disable debug mode
   */
  public setDebugMode(enabled: boolean): void {
    this.debugMode = enabled;
  }

  /**
   * Get detailed cache information
   */
  public getCacheInfo(): Array<{
    key: string;
    age: number;
    accessCount: number;
    size: number;
  }> {
    const now = Date.now();
    return Array.from(this.cache.entries()).map(([key, entry]) => ({
      key,
      age: now - entry.timestamp,
      accessCount: entry.accessCount,
      size: JSON.stringify(entry.data).length,
    }));
  }
}
