/**
 * ReactiveDataManager
 * 
 * Phase 2.1: Real-time State Synchronization
 * - Publish-subscribe pattern for state changes
 * - Event-driven architecture
 * - Automatic change detection and notification
 */

import { LazyDataManager } from './LazyDataManager';
import type { UnifiedLlmConfig } from '../types';

export interface StateChangeEvent {
  type: 'provider_updated' | 'role_updated' | 'assignment_updated' | 'view_updated' | 'loading_state_changed';
  entityId: string;
  changes: any;
  timestamp: string;
  source: 'user' | 'system' | 'sync';
}

export interface StateChangeSubscriber {
  (event: StateChangeEvent): void;
}

export interface Subscription {
  unsubscribe(): void;
}

interface SubscriberEntry {
  id: string;
  callback: StateChangeSubscriber;
  filter?: (event: StateChangeEvent) => boolean;
}

export class ReactiveDataManager extends LazyDataManager {
  private subscribers = new Map<string, Set<SubscriberEntry>>();
  private globalSubscribers = new Set<SubscriberEntry>();
  private eventHistory: StateChangeEvent[] = [];
  private maxHistorySize = 100;
  private eventQueue: StateChangeEvent[] = [];
  private isProcessingEvents = false;
  private debugMode = false;
  private enableHistory = false;

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
      debugMode?: boolean;
    }
  ) {
    super(initialData, options);
    
    if (options?.enableHistory) {
      this.enableHistory = options.enableHistory;
    }
    if (options?.maxHistorySize) {
      this.maxHistorySize = options.maxHistorySize;
    }
    if (options?.debugMode) {
      this.debugMode = options.debugMode;
    }
  }

  /**
   * Subscribe to specific event type
   */
  public subscribe(
    eventType: string,
    callback: StateChangeSubscriber,
    filter?: (event: StateChangeEvent) => boolean
  ): Subscription {
    const id = `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const entry: SubscriberEntry = { id, callback, filter };

    if (!this.subscribers.has(eventType)) {
      this.subscribers.set(eventType, new Set());
    }
    this.subscribers.get(eventType)!.add(entry);

    if (this.debugMode) {
      console.log(`[Subscribe] ${eventType} (id: ${id})`);
    }

    return {
      unsubscribe: () => {
        this.subscribers.get(eventType)?.delete(entry);
        if (this.debugMode) {
          console.log(`[Unsubscribe] ${eventType} (id: ${id})`);
        }
      },
    };
  }

  /**
   * Subscribe to all events (global)
   */
  public subscribeToAll(
    callback: StateChangeSubscriber,
    filter?: (event: StateChangeEvent) => boolean
  ): Subscription {
    const id = `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const entry: SubscriberEntry = { id, callback, filter };

    this.globalSubscribers.add(entry);

    if (this.debugMode) {
      console.log(`[Subscribe Global] (id: ${id})`);
    }

    return {
      unsubscribe: () => {
        this.globalSubscribers.delete(entry);
        if (this.debugMode) {
          console.log(`[Unsubscribe Global] (id: ${id})`);
        }
      },
    };
  }

  /**
   * Publish state change event
   */
  protected publish(event: StateChangeEvent): void {
    // Add to history
    if (this.enableHistory) {
      this.eventHistory.push(event);
      if (this.eventHistory.length > this.maxHistorySize) {
        this.eventHistory.shift();
      }
    }

    // Queue event for processing
    this.eventQueue.push(event);
    this.processEventQueue();
  }

  /**
   * Process event queue asynchronously
   */
  private processEventQueue(): void {
    if (this.isProcessingEvents || this.eventQueue.length === 0) return;

    this.isProcessingEvents = true;

    // Use setTimeout to ensure async processing
    setTimeout(() => {
      try {
        while (this.eventQueue.length > 0) {
          const event = this.eventQueue.shift()!;
          this.notifySubscribers(event);
        }
      } finally {
        this.isProcessingEvents = false;
      }
    }, 0);
  }

  /**
   * Notify all relevant subscribers
   */
  private notifySubscribers(event: StateChangeEvent): void {
    // Notify type-specific subscribers
    const typeSubscribers = this.subscribers.get(event.type);
    if (typeSubscribers) {
      typeSubscribers.forEach((entry) => {
        try {
          if (!entry.filter || entry.filter(event)) {
            entry.callback(event);
          }
        } catch (error) {
          console.error('[ReactiveDataManager] Error in subscriber callback:', error);
        }
      });
    }

    // Notify global subscribers
    this.globalSubscribers.forEach((entry) => {
      try {
        if (!entry.filter || entry.filter(event)) {
          entry.callback(event);
        }
      } catch (error) {
        console.error('[ReactiveDataManager] Error in global subscriber callback:', error);
      }
    });

    if (this.debugMode) {
      console.log(`[Publish] ${event.type} (${event.entityId})`);
    }
  }

  /**
   * Override updateViewData to publish events
   */
  public async updateViewData<T>(
    viewType: 'list' | 'visual' | 'deepTest',
    viewData: T,
    priority: number = 0
  ): Promise<UnifiedLlmConfig> {
    const oldData = JSON.parse(JSON.stringify(this.getUnifiedConfig()));
    
    const result = await super.updateViewData(viewType, viewData, priority);
    
    // Analyze and publish changes
    this.analyzeAndPublishChanges(oldData, result);
    
    // Publish view-specific event
    this.publish({
      type: 'view_updated',
      entityId: viewType,
      changes: { viewType, data: viewData },
      timestamp: new Date().toISOString(),
      source: 'user',
    });

    return result;
  }

  /**
   * Override updateUnifiedData to publish events
   */
  public async updateUnifiedData(
    updates: Partial<UnifiedLlmConfig>,
    priority: number = 0
  ): Promise<UnifiedLlmConfig> {
    const oldData = JSON.parse(JSON.stringify(this.getUnifiedConfig()));
    
    const result = await super.updateUnifiedData(updates, priority);
    
    // Analyze and publish changes
    this.analyzeAndPublishChanges(oldData, result);

    return result;
  }

  /**
   * Analyze changes and publish appropriate events
   */
  private analyzeAndPublishChanges(
    oldData: UnifiedLlmConfig,
    newData: UnifiedLlmConfig
  ): void {
    const timestamp = new Date().toISOString();

    // Analyze providers changes
    this.analyzeProviderChanges(oldData.providers, newData.providers, timestamp);

    // Analyze roles changes
    this.analyzeRoleChanges(oldData.roles, newData.roles, timestamp);

    // Analyze relationships/assignments changes
    this.analyzeAssignmentChanges(oldData, newData, timestamp);
  }

  /**
   * Analyze provider changes
   */
  private analyzeProviderChanges(
    oldProviders: UnifiedLlmConfig['providers'],
    newProviders: UnifiedLlmConfig['providers'],
    timestamp: string
  ): void {
    const oldKeys = Object.keys(oldProviders || {});
    const newKeys = Object.keys(newProviders || {});

    // Check for added providers
    newKeys.forEach((key) => {
      if (!oldKeys.includes(key)) {
        this.publish({
          type: 'provider_updated',
          entityId: key,
          changes: { action: 'added', provider: newProviders[key] },
          timestamp,
          source: 'user',
        });
      } else if (JSON.stringify(oldProviders[key]) !== JSON.stringify(newProviders[key])) {
        // Provider updated
        this.publish({
          type: 'provider_updated',
          entityId: key,
          changes: {
            action: 'updated',
            oldValue: oldProviders[key],
            newValue: newProviders[key],
          },
          timestamp,
          source: 'user',
        });
      }
    });

    // Check for removed providers
    oldKeys.forEach((key) => {
      if (!newKeys.includes(key)) {
        this.publish({
          type: 'provider_updated',
          entityId: key,
          changes: { action: 'removed', provider: oldProviders[key] },
          timestamp,
          source: 'user',
        });
      }
    });
  }

  /**
   * Analyze role changes
   */
  private analyzeRoleChanges(
    oldRoles: UnifiedLlmConfig['roles'],
    newRoles: UnifiedLlmConfig['roles'],
    timestamp: string
  ): void {
    const oldKeys = Object.keys(oldRoles || {});
    const newKeys = Object.keys(newRoles || {});

    // Check for added/updated roles
    newKeys.forEach((key) => {
      if (!oldKeys.includes(key)) {
        this.publish({
          type: 'role_updated',
          entityId: key,
          changes: { action: 'added', role: newRoles[key] },
          timestamp,
          source: 'user',
        });
      } else if (JSON.stringify(oldRoles[key]) !== JSON.stringify(newRoles[key])) {
        this.publish({
          type: 'role_updated',
          entityId: key,
          changes: {
            action: 'updated',
            oldValue: oldRoles[key],
            newValue: newRoles[key],
          },
          timestamp,
          source: 'user',
        });
      }
    });

    // Check for removed roles
    oldKeys.forEach((key) => {
      if (!newKeys.includes(key)) {
        this.publish({
          type: 'role_updated',
          entityId: key,
          changes: { action: 'removed', role: oldRoles[key] },
          timestamp,
          source: 'user',
        });
      }
    });
  }

  /**
   * Analyze assignment changes
   */
  private analyzeAssignmentChanges(
    oldData: UnifiedLlmConfig,
    newData: UnifiedLlmConfig,
    timestamp: string
  ): void {
    // This would analyze provider-role assignments
    // Simplified implementation - can be expanded based on specific needs
    if (JSON.stringify(oldData.roles) !== JSON.stringify(newData.roles)) {
      this.publish({
        type: 'assignment_updated',
        entityId: 'all',
        changes: { action: 'changed' },
        timestamp,
        source: 'user',
      });
    }
  }

  /**
   * Get event history
   */
  public getEventHistory(filter?: {
    type?: string;
    entityId?: string;
    since?: string;
  }): StateChangeEvent[] {
    if (!this.enableHistory) {
      return [];
    }

    let history = [...this.eventHistory];

    if (filter?.type) {
      history = history.filter((e) => e.type === filter.type);
    }
    if (filter?.entityId) {
      history = history.filter((e) => e.entityId === filter.entityId);
    }
    if (filter?.since) {
      const sinceTime = new Date(filter.since).getTime();
      history = history.filter((e) => new Date(e.timestamp).getTime() >= sinceTime);
    }

    return history;
  }

  /**
   * Clear event history
   */
  public clearEventHistory(): void {
    this.eventHistory = [];
  }

  /**
   * Get subscriber count
   */
  public getSubscriberCount(): {
    byType: Record<string, number>;
    global: number;
    total: number;
  } {
    let total = 0;
    const byType: Record<string, number> = {};

    this.subscribers.forEach((subscribers, type) => {
      byType[type] = subscribers.size;
      total += subscribers.size;
    });

    return {
      byType,
      global: this.globalSubscribers.size,
      total: total + this.globalSubscribers.size,
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
   * Enable/disable event history
   */
  public setHistoryEnabled(enabled: boolean): void {
    this.enableHistory = enabled;
    if (!enabled) {
      this.clearEventHistory();
    }
  }

  /**
   * Cleanup
   */
  public destroy(): void {
    // Clear all subscribers
    this.subscribers.clear();
    this.globalSubscribers.clear();
    this.eventHistory = [];
    this.eventQueue = [];

    super.destroy();
  }
}
