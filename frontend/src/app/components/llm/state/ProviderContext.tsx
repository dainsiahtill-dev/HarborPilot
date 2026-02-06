/**
 * Provider Context
 * 提供统一的状态管理和 actions
 */

import React, { createContext, useContext, useReducer, useCallback, useMemo } from 'react';
import type { ReactNode } from 'react';
import type { 
  ProviderState, 
  ProviderAction, 
  RoleIdStrict, 
  ConnectivityResultStrict,
  InterviewSuiteReportStrict,
  TestStatus,
  ConnectivityStatus,
} from './providerReducer';
import { 
  providerReducer, 
  initialProviderState, 
  ProviderActions 
} from './providerReducer';

// ============================================================================
// Context Type
// ============================================================================

interface ProviderContextValue {
  // State
  state: ProviderState;
  
  // Actions - Selection
  selectRole: (role: RoleIdStrict) => void;
  selectProvider: (id: string | null) => void;
  selectMethod: (method: 'sdk' | 'api' | 'cli') => void;
  
  // Actions - View
  switchTab: (tab: 'config' | 'deepTest') => void;
  setConfigView: (view: 'list' | 'visual') => void;
  setDeepView: (view: 'hall' | 'session') => void;
  setInterviewMode: (mode: 'interactive' | 'auto') => void;
  
  // Actions - Provider Edit
  startEditProvider: (id: string) => void;
  stopEditProvider: () => void;
  toggleExpandProvider: (id: string) => void;
  collapseAllProviders: () => void;
  
  // Actions - Test
  openTestPanel: (id: string) => void;
  closeTestPanel: () => void;
  startTest: (id: string) => void;
  completeTest: (id: string, success: boolean) => void;
  cancelTest: () => void;
  
  // Actions - Connectivity
  startConnectivityTest: (key: string) => void;
  completeConnectivityTest: (key: string, result: ConnectivityResultStrict) => void;
  
  // Actions - Interview
  openInterviewPanel: () => void;
  closeInterviewPanel: () => void;
  startInterview: () => void;
  completeInterview: (report: InterviewSuiteReportStrict) => void;
  failInterview: (error: string) => void;
  cancelInterview: () => void;
  
  // Actions - Error
  setError: (error: string | null) => void;
  clearError: () => void;
  
  // Direct dispatch (for complex cases)
  dispatch: React.Dispatch<ProviderAction>;
}

// ============================================================================
// Context Creation
// ============================================================================

const ProviderContext = createContext<ProviderContextValue | null>(null);

// ============================================================================
// Provider Component
// ============================================================================

interface ProviderContextProviderProps {
  children: ReactNode;
  initialState?: Partial<ProviderState>;
}

export function ProviderContextProvider({ 
  children, 
  initialState 
}: ProviderContextProviderProps) {
  const [state, dispatch] = useReducer(
    providerReducer,
    { ...initialProviderState, ...initialState }
  );

  // ==========================================================================
  // Selection Actions
  // ==========================================================================
  const selectRole = useCallback((role: RoleIdStrict) => {
    dispatch(ProviderActions.selectRole(role));
  }, []);

  const selectProvider = useCallback((id: string | null) => {
    dispatch(ProviderActions.selectProvider(id));
  }, []);

  const selectMethod = useCallback((method: 'sdk' | 'api' | 'cli') => {
    dispatch(ProviderActions.selectMethod(method));
  }, []);

  // ==========================================================================
  // View Actions
  // ==========================================================================
  const switchTab = useCallback((tab: 'config' | 'deepTest') => {
    dispatch(ProviderActions.switchTab(tab));
  }, []);

  const setConfigView = useCallback((view: 'list' | 'visual') => {
    dispatch(ProviderActions.setConfigView(view));
  }, []);

  const setDeepView = useCallback((view: 'hall' | 'session') => {
    dispatch(ProviderActions.setDeepView(view));
  }, []);

  const setInterviewMode = useCallback((mode: 'interactive' | 'auto') => {
    dispatch(ProviderActions.setInterviewMode(mode));
  }, []);

  // ==========================================================================
  // Provider Edit Actions
  // ==========================================================================
  const startEditProvider = useCallback((id: string) => {
    dispatch(ProviderActions.startEditProvider(id));
  }, []);

  const stopEditProvider = useCallback(() => {
    dispatch(ProviderActions.stopEditProvider());
  }, []);

  const toggleExpandProvider = useCallback((id: string) => {
    dispatch(ProviderActions.toggleExpandProvider(id));
  }, []);

  const collapseAllProviders = useCallback(() => {
    dispatch(ProviderActions.collapseAllProviders());
  }, []);

  // ==========================================================================
  // Test Actions
  // ==========================================================================
  const openTestPanel = useCallback((id: string) => {
    dispatch(ProviderActions.openTestPanel(id));
  }, []);

  const closeTestPanel = useCallback(() => {
    dispatch(ProviderActions.closeTestPanel());
  }, []);

  const startTest = useCallback((id: string) => {
    dispatch(ProviderActions.startTest(id));
  }, []);

  const completeTest = useCallback((id: string, success: boolean) => {
    dispatch(ProviderActions.completeTest(id, success));
  }, []);

  const cancelTest = useCallback(() => {
    dispatch(ProviderActions.cancelTest());
  }, []);

  // ==========================================================================
  // Connectivity Actions
  // ==========================================================================
  const startConnectivityTest = useCallback((key: string) => {
    dispatch(ProviderActions.startConnectivityTest(key));
  }, []);

  const completeConnectivityTest = useCallback((key: string, result: ConnectivityResultStrict) => {
    dispatch(ProviderActions.completeConnectivityTest(key, result));
  }, []);

  // ==========================================================================
  // Interview Actions
  // ==========================================================================
  const openInterviewPanel = useCallback(() => {
    dispatch(ProviderActions.openInterviewPanel());
  }, []);

  const closeInterviewPanel = useCallback(() => {
    dispatch(ProviderActions.closeInterviewPanel());
  }, []);

  const startInterview = useCallback(() => {
    dispatch(ProviderActions.startInterview());
  }, []);

  const completeInterview = useCallback((report: InterviewSuiteReportStrict) => {
    dispatch(ProviderActions.completeInterview(report));
  }, []);

  const failInterview = useCallback((error: string) => {
    dispatch(ProviderActions.failInterview(error));
  }, []);

  const cancelInterview = useCallback(() => {
    dispatch(ProviderActions.cancelInterview());
  }, []);

  // ==========================================================================
  // Error Actions
  // ==========================================================================
  const setError = useCallback((error: string | null) => {
    dispatch(ProviderActions.setError(error));
  }, []);

  const clearError = useCallback(() => {
    dispatch(ProviderActions.clearError());
  }, []);

  // ==========================================================================
  // Memoized Value
  // ==========================================================================
  const value = useMemo<ProviderContextValue>(
    () => ({
      state,
      selectRole,
      selectProvider,
      selectMethod,
      switchTab,
      setConfigView,
      setDeepView,
      setInterviewMode,
      startEditProvider,
      stopEditProvider,
      toggleExpandProvider,
      collapseAllProviders,
      openTestPanel,
      closeTestPanel,
      startTest,
      completeTest,
      cancelTest,
      startConnectivityTest,
      completeConnectivityTest,
      openInterviewPanel,
      closeInterviewPanel,
      startInterview,
      completeInterview,
      failInterview,
      cancelInterview,
      setError,
      clearError,
      dispatch,
    }),
    [
      state,
      selectRole,
      selectProvider,
      selectMethod,
      switchTab,
      setConfigView,
      setDeepView,
      setInterviewMode,
      startEditProvider,
      stopEditProvider,
      toggleExpandProvider,
      collapseAllProviders,
      openTestPanel,
      closeTestPanel,
      startTest,
      completeTest,
      cancelTest,
      startConnectivityTest,
      completeConnectivityTest,
      openInterviewPanel,
      closeInterviewPanel,
      startInterview,
      completeInterview,
      failInterview,
      cancelInterview,
      setError,
      clearError,
      dispatch,
    ]
  );

  return (
    <ProviderContext.Provider value={value}>
      {children}
    </ProviderContext.Provider>
  );
}

// ============================================================================
// Hook
// ============================================================================

export function useProviderContext(): ProviderContextValue {
  const context = useContext(ProviderContext);
  if (!context) {
    throw new Error('useProviderContext must be used within ProviderContextProvider');
  }
  return context;
}

// ============================================================================
// Selectors (for performance)
// ============================================================================

export function useSelectedRole(): RoleIdStrict {
  const { state } = useProviderContext();
  return state.selectedRole;
}

export function useSelectedProvider(): string | null {
  const { state } = useProviderContext();
  return state.selectedProviderId;
}

export function useActiveTab(): 'config' | 'deepTest' {
  const { state } = useProviderContext();
  return state.activeTab;
}

export function useTestPanelState(): { selectedProviderId: string | null; status: TestStatus } {
  const { state } = useProviderContext();
  return state.testPanel;
}

export function useInterviewPanelState(): { 
  open: boolean; 
  status: TestStatus; 
  error: string | null;
  report: InterviewSuiteReportStrict | null;
} {
  const { state } = useProviderContext();
  return state.interviewPanel;
}

export function useConnectivityStatus(providerId: string): ConnectivityStatus {
  const { state } = useProviderContext();
  return state.providerTestStatus[providerId] || 'unknown';
}

export function useIsProviderExpanded(providerId: string): boolean {
  const { state } = useProviderContext();
  return state.expandedProviders.has(providerId);
}
