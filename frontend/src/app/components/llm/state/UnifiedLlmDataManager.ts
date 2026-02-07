
import type { UnifiedLlmConfig } from '../types';
import type { ViewAdapter } from '../adapters/types';
import { ListViewAdapter, ListViewData, ListViewState } from '../adapters/ListViewAdapter';
import { VisualViewAdapter, VisualViewData, VisualViewState } from '../adapters/VisualViewAdapter';
import { DeepTestViewAdapter, DeepTestViewData, DeepTestViewState } from '../adapters/DeepTestViewAdapter';

// Simple deep merge utility
function deepMerge(target: any, source: any): any {
  if (typeof target !== 'object' || target === null) {
    return source;
  }
  if (typeof source !== 'object' || source === null) {
    return source;
  }
  
  const result = Array.isArray(target) ? [...target] : { ...target };
  
  for (const key in source) {
    if (Object.prototype.hasOwnProperty.call(source, key)) {
      if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
        result[key] = deepMerge(result[key], source[key]);
      } else {
        result[key] = source[key];
      }
    }
  }
  return result;
}

// Simple hash utility (placeholder for real hash)
function calculateHash(data: any): string {
  // In a real app, use a proper hashing function. 
  // Here we just use a simple string length + timestamp combo for changing detection
  return `${JSON.stringify(data).length}-${Date.now()}`;
}

export class UnifiedLlmDataManager {
  protected unifiedData: UnifiedLlmConfig;
  private adapters: Map<string, ViewAdapter<any, any>>;
  
  constructor(initialData: UnifiedLlmConfig) {
    this.unifiedData = JSON.parse(JSON.stringify(initialData)); // Deep copy to avoid mutation reference issues
    this.adapters = new Map();
    this.registerAdapters();
  }
  
  private registerAdapters() {
    this.adapters.set('list', new ListViewAdapter());
    this.adapters.set('visual', new VisualViewAdapter());
    this.adapters.set('deepTest', new DeepTestViewAdapter());
  }
  
  public getUnifiedConfig(): UnifiedLlmConfig {
    return this.unifiedData;
  }
  
  // Get view data for a specific view type
  public getViewData<T>(viewType: 'list' | 'visual' | 'deepTest'): T {
    const adapter = this.adapters.get(viewType);
    if (!adapter) {
      throw new Error(`Unknown view type: ${viewType}`);
    }
    return adapter.adaptToView(this.unifiedData) as T;
  }
  
  // Update view data from a specific view, merging changes back to unified config
  public updateViewData<T>(viewType: 'list' | 'visual' | 'deepTest', viewData: T): UnifiedLlmConfig {
    const adapter = this.adapters.get(viewType);
    if (!adapter) {
      throw new Error(`Unknown view type: ${viewType}`);
    }
    
    // transform view data back to partial unified config
    const updates = adapter.adaptFromView(viewData, this.unifiedData);
    
    // apply updates
    this.applyUpdates(updates);
    
    return this.unifiedData;
  }
  
  // Direct update to unified config (e.g., from generic actions or initial load)
  public updateUnifiedData(updates: Partial<UnifiedLlmConfig>): UnifiedLlmConfig {
    this.applyUpdates(updates);
    return this.unifiedData;
  }
  
  private applyUpdates(updates: Partial<UnifiedLlmConfig>): void {
    // Deep merge updates into unifiedData
    this.unifiedData = deepMerge(this.unifiedData, updates);
    
    // Update metadata
    if (!this.unifiedData.metadata) {
        this.unifiedData.metadata = {
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            version: '1.0.0',
            integrity_hash: ''
        };
    }
    this.unifiedData.metadata.updated_at = new Date().toISOString();
    this.unifiedData.metadata.integrity_hash = calculateHash(this.unifiedData);
  }
  
  // Helper to get initial state for a view
  public getInitialViewState(viewType: 'list' | 'visual' | 'deepTest'): any {
    const adapter = this.adapters.get(viewType);
    if (!adapter) return {};
    return adapter.createViewState();
  }
}
