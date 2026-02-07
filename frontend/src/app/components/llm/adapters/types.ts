import type { UnifiedLlmConfig } from '../types';

export interface ViewActions {
  [key: string]: (...args: any[]) => void;
}

export interface ViewAdapter<TViewData, TViewState> {
  // Data Transformation
  adaptToView(unifiedData: UnifiedLlmConfig): TViewData;
  adaptFromView(viewData: TViewData, unifiedData: UnifiedLlmConfig): Partial<UnifiedLlmConfig>;
  
  // State Management
  createViewState(): TViewState;
  updateViewState?(state: TViewState, changes: Partial<TViewState>): TViewState;
  
  // Optional: View specific actions that might update the unified config
  getViewActions?(viewData: TViewData): ViewActions;
}
