/**
 * Provider State Management - Reducer Pattern
 * 统一处理所有 Provider 相关状态，替代分散的 useState
 */

import type { RoleIdStrict, ProviderConfigStrict, ConnectivityResultStrict, InterviewSuiteReportStrict } from '../types/strict';
import type { ProviderConfig } from '../types';

// ============================================================================
// State Types
// ============================================================================

/** 连接性测试状态 */
export type ConnectivityStatus = 'unknown' | 'running' | 'success' | 'failed';

/** 测试状态 */
export type TestStatus = 'idle' | 'running' | 'success' | 'failed';

/** 配置视图 */
export type ConfigView = 'list' | 'visual';

/** 深度测试视图 */
export type DeepView = 'hall' | 'session';

/** 面试模式 */
export type InterviewMode = 'interactive' | 'auto';

/** 活跃标签 */
export type ActiveTab = 'config' | 'deepTest';

/** 连接方式 */
export type ConnectionMethodId = 'sdk' | 'api' | 'cli';

/** 面试面板状态 */
export interface InterviewPanelState {
  open: boolean;
  status: TestStatus;
  report: InterviewSuiteReportStrict | null;
  error: string | null;
}

/** 测试面板状态 */
export interface TestPanelState {
  selectedProviderId: string | null;
  status: TestStatus;
  cancelled: boolean;
}

/** Provider 状态 */
export interface ProviderState {
  // 选择状态
  selectedRole: RoleIdStrict;
  selectedProviderId: string | null;
  selectedMethod: ConnectionMethodId;
  
  // 视图状态
  activeTab: ActiveTab;
  configView: ConfigView;
  deepView: DeepView;
  interviewMode: InterviewMode;
  
  // Provider 编辑状态
  editingProvider: string | null;
  expandedProviders: Set<string>;
  
  // 测试状态
  testPanel: TestPanelState;
  providerTestStatus: Record<string, ConnectivityStatus>;
  connectivityResults: Map<string, ConnectivityResultStrict>;
  connectivityRunning: boolean;
  connectivityRunningKey: string | null;
  
  // 面试状态
  interviewPanel: InterviewPanelState;
  interviewRunning: boolean;
  interviewCancelled: boolean;
  
  // 错误状态
  globalError: string | null;
}

// ============================================================================
// Action Types
// ============================================================================

export type ProviderAction =
  // 选择相关
  | { type: 'SELECT_ROLE'; payload: RoleIdStrict }
  | { type: 'SELECT_PROVIDER'; payload: string | null }
  | { type: 'SELECT_METHOD'; payload: ConnectionMethodId }
  
  // 视图切换
  | { type: 'SWITCH_TAB'; payload: ActiveTab }
  | { type: 'SET_CONFIG_VIEW'; payload: ConfigView }
  | { type: 'SET_DEEP_VIEW'; payload: DeepView }
  | { type: 'SET_INTERVIEW_MODE'; payload: InterviewMode }
  
  // Provider 编辑
  | { type: 'START_EDIT_PROVIDER'; payload: string }
  | { type: 'STOP_EDIT_PROVIDER' }
  | { type: 'TOGGLE_EXPAND_PROVIDER'; payload: string }
  | { type: 'EXPAND_ALL_PROVIDERS' }
  | { type: 'COLLAPSE_ALL_PROVIDERS' }
  
  // 测试相关
  | { type: 'OPEN_TEST_PANEL'; payload: string }
  | { type: 'CLOSE_TEST_PANEL' }
  | { type: 'START_TEST'; payload: string }
  | { type: 'COMPLETE_TEST'; payload: { providerId: string; success: boolean } }
  | { type: 'CANCEL_TEST' }
  | { type: 'SET_PROVIDER_TEST_STATUS'; payload: { providerId: string; status: ConnectivityStatus } }
  
  // 连通性测试
  | { type: 'START_CONNECTIVITY_TEST'; payload: string }
  | { type: 'COMPLETE_CONNECTIVITY_TEST'; payload: { key: string; result: ConnectivityResultStrict } }
  | { type: 'CLEAR_CONNECTIVITY_RESULT'; payload: string }
  
  // 面试相关
  | { type: 'OPEN_INTERVIEW_PANEL' }
  | { type: 'CLOSE_INTERVIEW_PANEL' }
  | { type: 'START_INTERVIEW' }
  | { type: 'COMPLETE_INTERVIEW'; payload: InterviewSuiteReportStrict }
  | { type: 'FAIL_INTERVIEW'; payload: string }
  | { type: 'CANCEL_INTERVIEW' }
  
  // 错误处理
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'CLEAR_ERROR' }
  
  // 批量更新（用于初始化或外部更新）
  | { type: 'HYDRATE_STATE'; payload: Partial<ProviderState> };

// ============================================================================
// Initial State
// ============================================================================

export const initialProviderState: ProviderState = {
  selectedRole: 'pm',
  selectedProviderId: null,
  selectedMethod: 'sdk',
  
  activeTab: 'config',
  configView: 'list',
  deepView: 'hall',
  interviewMode: 'interactive',
  
  editingProvider: null,
  expandedProviders: new Set(),
  
  testPanel: {
    selectedProviderId: null,
    status: 'idle',
    cancelled: false,
  },
  providerTestStatus: {},
  connectivityResults: new Map(),
  connectivityRunning: false,
  connectivityRunningKey: null,
  
  interviewPanel: {
    open: false,
    status: 'idle',
    report: null,
    error: null,
  },
  interviewRunning: false,
  interviewCancelled: false,
  
  globalError: null,
};

// ============================================================================
// Reducer
// ============================================================================

export function providerReducer(state: ProviderState, action: ProviderAction): ProviderState {
  switch (action.type) {
    // 选择相关
    case 'SELECT_ROLE': {
      return {
        ...state,
        selectedRole: action.payload,
        // 清理相关状态
        interviewPanel: {
          ...state.interviewPanel,
          error: null,
        },
      };
    }
    
    case 'SELECT_PROVIDER': {
      return {
        ...state,
        selectedProviderId: action.payload,
      };
    }
    
    case 'SELECT_METHOD': {
      return {
        ...state,
        selectedMethod: action.payload,
      };
    }
    
    // 视图切换
    case 'SWITCH_TAB': {
      const newTab = action.payload;
      const updates: Partial<ProviderState> = { activeTab: newTab };
      
      // 切换标签时清理状态
      if (newTab !== 'config') {
        updates.testPanel = initialProviderState.testPanel;
      }
      if (newTab !== 'deepTest') {
        updates.interviewPanel = initialProviderState.interviewPanel;
      }
      
      return { ...state, ...updates };
    }
    
    case 'SET_CONFIG_VIEW': {
      return {
        ...state,
        configView: action.payload,
      };
    }
    
    case 'SET_DEEP_VIEW': {
      return {
        ...state,
        deepView: action.payload,
      };
    }
    
    case 'SET_INTERVIEW_MODE': {
      return {
        ...state,
        interviewMode: action.payload,
        // 切换模式时重置视图
        deepView: action.payload === 'auto' ? 'hall' : state.deepView,
      };
    }
    
    // Provider 编辑
    case 'START_EDIT_PROVIDER': {
      return {
        ...state,
        editingProvider: action.payload,
      };
    }
    
    case 'STOP_EDIT_PROVIDER': {
      return {
        ...state,
        editingProvider: null,
      };
    }
    
    case 'TOGGLE_EXPAND_PROVIDER': {
      const newExpanded = new Set(state.expandedProviders);
      if (newExpanded.has(action.payload)) {
        newExpanded.delete(action.payload);
      } else {
        newExpanded.add(action.payload);
      }
      return {
        ...state,
        expandedProviders: newExpanded,
      };
    }
    
    case 'EXPAND_ALL_PROVIDERS': {
      // 注意：这里需要在组件层注入 providerIds
      return state;
    }
    
    case 'COLLAPSE_ALL_PROVIDERS': {
      return {
        ...state,
        expandedProviders: new Set(),
      };
    }
    
    // 测试相关
    case 'OPEN_TEST_PANEL': {
      return {
        ...state,
        testPanel: {
          selectedProviderId: action.payload,
          status: 'idle',
          cancelled: false,
        },
      };
    }
    
    case 'CLOSE_TEST_PANEL': {
      return {
        ...state,
        testPanel: initialProviderState.testPanel,
      };
    }
    
    case 'START_TEST': {
      return {
        ...state,
        testPanel: {
          ...state.testPanel,
          status: 'running',
          cancelled: false,
        },
        providerTestStatus: {
          ...state.providerTestStatus,
          [action.payload]: 'running',
        },
      };
    }
    
    case 'COMPLETE_TEST': {
      const { providerId, success } = action.payload;
      return {
        ...state,
        testPanel: {
          ...state.testPanel,
          status: success ? 'success' : 'failed',
        },
        providerTestStatus: {
          ...state.providerTestStatus,
          [providerId]: success ? 'success' : 'failed',
        },
      };
    }
    
    case 'CANCEL_TEST': {
      const providerId = state.testPanel.selectedProviderId;
      return {
        ...state,
        testPanel: {
          ...state.testPanel,
          status: 'failed',
          cancelled: true,
        },
        providerTestStatus: {
          ...state.providerTestStatus,
          ...(providerId && { [providerId]: 'unknown' }),
        },
      };
    }
    
    case 'SET_PROVIDER_TEST_STATUS': {
      const { providerId, status } = action.payload;
      return {
        ...state,
        providerTestStatus: {
          ...state.providerTestStatus,
          [providerId]: status,
        },
      };
    }
    
    // 连通性测试
    case 'START_CONNECTIVITY_TEST': {
      return {
        ...state,
        connectivityRunning: true,
        connectivityRunningKey: action.payload,
      };
    }
    
    case 'COMPLETE_CONNECTIVITY_TEST': {
      const { key, result } = action.payload;
      const newResults = new Map(state.connectivityResults);
      newResults.set(key, result);
      return {
        ...state,
        connectivityResults: newResults,
        connectivityRunning: false,
        connectivityRunningKey: null,
      };
    }
    
    case 'CLEAR_CONNECTIVITY_RESULT': {
      const newResults = new Map(state.connectivityResults);
      newResults.delete(action.payload);
      return {
        ...state,
        connectivityResults: newResults,
      };
    }
    
    // 面试相关
    case 'OPEN_INTERVIEW_PANEL': {
      return {
        ...state,
        interviewPanel: {
          ...state.interviewPanel,
          open: true,
          status: 'idle',
          error: null,
        },
      };
    }
    
    case 'CLOSE_INTERVIEW_PANEL': {
      return {
        ...state,
        interviewPanel: initialProviderState.interviewPanel,
      };
    }
    
    case 'START_INTERVIEW': {
      return {
        ...state,
        interviewRunning: true,
        interviewCancelled: false,
        interviewPanel: {
          ...state.interviewPanel,
          status: 'running',
          error: null,
          report: null,
        },
      };
    }
    
    case 'COMPLETE_INTERVIEW': {
      return {
        ...state,
        interviewRunning: false,
        interviewPanel: {
          ...state.interviewPanel,
          status: 'success',
          report: action.payload,
        },
      };
    }
    
    case 'FAIL_INTERVIEW': {
      return {
        ...state,
        interviewRunning: false,
        interviewPanel: {
          ...state.interviewPanel,
          status: 'failed',
          error: action.payload,
        },
      };
    }
    
    case 'CANCEL_INTERVIEW': {
      return {
        ...state,
        interviewRunning: false,
        interviewCancelled: true,
        interviewPanel: {
          ...state.interviewPanel,
          status: 'failed',
          error: '面试已取消',
        },
      };
    }
    
    // 错误处理
    case 'SET_ERROR': {
      return {
        ...state,
        globalError: action.payload,
      };
    }
    
    case 'CLEAR_ERROR': {
      return {
        ...state,
        globalError: null,
      };
    }
    
    // 批量更新
    case 'HYDRATE_STATE': {
      return {
        ...state,
        ...action.payload,
      };
    }
    
    default: {
      return state;
    }
  }
}

// ============================================================================
// Action Creators
// ============================================================================

export const ProviderActions = {
  selectRole: (role: RoleIdStrict): ProviderAction => ({ type: 'SELECT_ROLE', payload: role }),
  selectProvider: (id: string | null): ProviderAction => ({ type: 'SELECT_PROVIDER', payload: id }),
  selectMethod: (method: ConnectionMethodId): ProviderAction => ({ type: 'SELECT_METHOD', payload: method }),
  
  switchTab: (tab: ActiveTab): ProviderAction => ({ type: 'SWITCH_TAB', payload: tab }),
  setConfigView: (view: ConfigView): ProviderAction => ({ type: 'SET_CONFIG_VIEW', payload: view }),
  setDeepView: (view: DeepView): ProviderAction => ({ type: 'SET_DEEP_VIEW', payload: view }),
  setInterviewMode: (mode: InterviewMode): ProviderAction => ({ type: 'SET_INTERVIEW_MODE', payload: mode }),
  
  startEditProvider: (id: string): ProviderAction => ({ type: 'START_EDIT_PROVIDER', payload: id }),
  stopEditProvider: (): ProviderAction => ({ type: 'STOP_EDIT_PROVIDER' }),
  toggleExpandProvider: (id: string): ProviderAction => ({ type: 'TOGGLE_EXPAND_PROVIDER', payload: id }),
  collapseAllProviders: (): ProviderAction => ({ type: 'COLLAPSE_ALL_PROVIDERS' }),
  
  openTestPanel: (id: string): ProviderAction => ({ type: 'OPEN_TEST_PANEL', payload: id }),
  closeTestPanel: (): ProviderAction => ({ type: 'CLOSE_TEST_PANEL' }),
  startTest: (id: string): ProviderAction => ({ type: 'START_TEST', payload: id }),
  completeTest: (id: string, success: boolean): ProviderAction => ({ 
    type: 'COMPLETE_TEST', 
    payload: { providerId: id, success } 
  }),
  cancelTest: (): ProviderAction => ({ type: 'CANCEL_TEST' }),
  
  startConnectivityTest: (key: string): ProviderAction => ({ 
    type: 'START_CONNECTIVITY_TEST', 
    payload: key 
  }),
  completeConnectivityTest: (key: string, result: ConnectivityResultStrict): ProviderAction => ({ 
    type: 'COMPLETE_CONNECTIVITY_TEST', 
    payload: { key, result } 
  }),
  
  openInterviewPanel: (): ProviderAction => ({ type: 'OPEN_INTERVIEW_PANEL' }),
  closeInterviewPanel: (): ProviderAction => ({ type: 'CLOSE_INTERVIEW_PANEL' }),
  startInterview: (): ProviderAction => ({ type: 'START_INTERVIEW' }),
  completeInterview: (report: InterviewSuiteReportStrict): ProviderAction => ({ 
    type: 'COMPLETE_INTERVIEW', 
    payload: report 
  }),
  failInterview: (error: string): ProviderAction => ({ type: 'FAIL_INTERVIEW', payload: error }),
  cancelInterview: (): ProviderAction => ({ type: 'CANCEL_INTERVIEW' }),
  
  setError: (error: string | null): ProviderAction => ({ type: 'SET_ERROR', payload: error }),
  clearError: (): ProviderAction => ({ type: 'CLEAR_ERROR' }),
} as const;
