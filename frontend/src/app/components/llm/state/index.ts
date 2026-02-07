/**
 * State Management Exports
 * 
 * Complete state management system with:
 * - Provider Context for React state management
 * - Optimized Data Managers for performance
 * - View Adapters for data transformation
 */

// ============================================================================
// Provider Reducer & Actions
// ============================================================================

export { 
  providerReducer, 
  initialProviderState, 
  ProviderActions 
} from './providerReducer';

export type { 
  ProviderState, 
  ProviderAction,
  ConnectivityStatus,
  TestStatus,
  ConfigView,
  DeepView,
  InterviewMode,
  ActiveTab,
  ConnectionMethodId,
  InterviewPanelState,
  TestPanelState,
  ConnectivityResultStrict,
} from './providerReducer';

// ============================================================================
// Provider Context & Hooks
// ============================================================================

export { 
  ProviderContextProvider, 
  useProviderContext,
  useSelectedRole,
  useSelectedProvider,
  useActiveTab,
  useTestPanelState,
  useInterviewPanelState,
  useConnectivityStatus,
  useIsProviderExpanded,
  // 新的统一编辑状态 Selectors
  useEditingProviderId,
  useEditFormState,
  useHasPendingChanges,
  useIsSavingProvider,
  useProviderError,
  useGlobalPendingChangesCount,
} from './ProviderContext';

// ============================================================================
// Unified Edit State Hooks (New)
// ============================================================================

export {
  useProviderForm,
  useProviderFormList,
  type UseProviderFormOptions,
  type UseProviderFormReturn,
} from './useProviderForm';

// ============================================================================
// Optimized Data Managers (Phase 1-4)
// ============================================================================

// Phase 1.1: Cache Layer Enhancement
export { OptimizedDataManager } from './OptimizedDataManager';
export type { CacheStats } from './OptimizedDataManager';

// Phase 1.2 & 1.3: Batch & Lazy Loading (extends OptimizedDataManager)
// Note: These use inheritance - import directly from module if needed
// export { BatchDataManager } from './BatchDataManager';
// export { LazyDataManager } from './LazyDataManager';

// Phase 2: State Synchronization (extends LazyDataManager)
// export { ReactiveDataManager } from './ReactiveDataManager';
// export { ConflictAwareDataManager } from './ConflictAwareDataManager';
// export type { StateChangeEvent, StateChangeSubscriber, Subscription } from './ReactiveDataManager';
// export type { ConflictInfo, ConflictResolution, ConflictResolutionStrategy, UpdateResult } from './ConflictAwareDataManager';

// Phase 3: UX Optimizations (extends ConflictAwareDataManager)
// export { OptimisticDataManager } from './OptimisticDataManager';
// export type { LoadingState, OptimisticUpdate, OptimisticResult } from './OptimisticDataManager';

// Phase 4: Debug Tools (extends OptimisticDataManager)
// export { DebuggableDataManager } from './DebuggableDataManager';
// export type { DebugInfo, PerformanceMetrics, StateSnapshot } from './DebuggableDataManager';

// Re-export base data manager
export { UnifiedLlmDataManager } from './UnifiedLlmDataManager';

// ============================================================================
// Connectivity Store
// ============================================================================

export {
  useConnectivityStore,
  useRoleProviderConnectivity,
  useProviderReadiness,
  type InterviewProviderSummary,
  type ConnectivityResult,
  type InterviewRoleSummary,
} from './connectivityStore';

// ============================================================================
// Utilities
// ============================================================================

export {
  calculateConnectivityStatus,
  formatConnectivityStatus,
  getConnectivityStatusColor,
  getConnectivityStatusBgColor,
  getConnectivityStatusDotColor,
  isCacheExpired,
  type ConnectivityResult as SimpleConnectivityResult,
} from '../utils/connectivity';

// ============================================================================
// Types
// ============================================================================

export type { RoleId } from '../interview/InterviewHall';
