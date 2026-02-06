/**
 * State Management Exports
 */

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
} from './ProviderContext';

export {
  useConnectivityStore,
  useRoleProviderConnectivity,
  useProviderReadiness,
  type InterviewProviderSummary,
  type ConnectivityResult,
  type InterviewRoleSummary,
} from './connectivityStore';

export type { RoleId } from '../interview/InterviewHall';
