/**
 * LLMSettingsTab
 * LLM 设置主组件，使用 Context + Reducer 模式
 */

import React, { useCallback, useEffect, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Loader2, CheckCircle2, AlertTriangle, PlayCircle } from 'lucide-react';

import { 
  ProviderContextProvider, 
  useProviderContext,
  useSelectedRole,
  useConnectivityStore,
  type RoleId,
} from './state';
import type { ProviderState } from './state';
import { ProviderListManager } from './providers';

import type { 
  ProviderConfig, 
  ProviderKind, 
  SimpleProvider,
} from './types';
import { PROVIDER_KINDS, isCLIProviderType } from './types';
import type { TestEvent, TestResult } from './test/types';
import { TestPanel } from './test/TestPanel';
import { useTestEvents } from './test/hooks/useTestEvents';
import { useProviderRegistry } from './ProviderRegistry';
import { LLMVisualEditor } from './visual/LLMVisualEditor';
import type { VisualGraphConfig, VisualGraphStatus } from './visual/types/visual';

import { 
  InterviewHall, 
  type ConnectivityResult as InterviewConnectivityResult,
} from './interview/InterviewHall';
import { InterviewSession } from './interview/InterviewSession';
import { 
  InteractiveInterviewHall, 
  type InteractiveInterviewAnswer,
  type InteractiveInterviewReport,
} from './interview/InteractiveInterviewHall';

// ============================================================================
// Types
// ============================================================================

interface LlmConfig {
  schema_version: number;
  providers: Record<string, ProviderConfig>;
  roles: Record<string, {
    provider_id?: string;
    model?: string;
    profile?: string;
  }>;
  policies?: {
    required_ready_roles?: string[];
    test_required_suites?: string[];
    role_requirements?: Record<string, {
      requires_thinking?: boolean;
      min_confidence?: number;
      error_message?: string;
    }>;
  };
}

interface LlmStatus {
  state: string;
  required_ready_roles: string[];
  blocked_roles: string[];
  unsupported_roles: string[];
  roles: Record<string, {
    provider_id?: string;
    model?: string;
    profile?: string;
    ready?: boolean;
    grade?: string;
    last_run_id?: string | null;
    timestamp?: string | null;
    suites?: Record<string, unknown> | null;
    runtime_supported?: boolean;
  }>;
  providers?: Record<string, {
    ready?: boolean | null;
    grade?: string;
    last_run_id?: string | null;
    timestamp?: string | null;
    suites?: Record<string, unknown> | null;
    model?: string | null;
    role?: string | null;
  }>;
  interviews?: {
    lastUpdated: string | null;
    latest_by_provider: Record<string, {
      id: string;
      role: string;
      provider_id: string;
      model: string;
      status: 'passed' | 'failed';
      timestamp: string;
      report_path: string;
    }>;
    latest_by_role_provider_model: Record<string, {
      id: string;
      role: string;
      provider_id: string;
      model: string;
      status: 'passed' | 'failed';
      timestamp: string;
      report_path: string;
    }>;
  };
}

interface LLMSettingsTabProps {
  llmConfig: LlmConfig | null;
  llmStatus: LlmStatus | null;
  llmLoading: boolean;
  llmSaving: boolean;
  llmError: string | null;
  deletingProviders?: Record<string, boolean>;
  onSaveConfig: () => void;
  onRunInterview: (
    role: RoleId,
    providerId: string,
    model: string,
    onEvent?: (event: TestEvent) => void
  ) => Promise<Record<string, unknown> | null>;
  onRunConnectivityTest: (
    role: RoleId,
    providerId: string,
    model: string
  ) => Promise<Record<string, unknown> | null>;
  onAskInteractiveInterview: (payload: {
    roleId: RoleId;
    providerId: string;
    model: string;
    question: string;
    expectedCriteria?: string[];
    expectsThinking?: boolean;
    sessionId?: string | null;
    context?: Array<{ question: string; answer: string }>;
  }) => Promise<InteractiveInterviewAnswer | null>;
  onSaveInteractiveInterview: (payload: {
    roleId: RoleId;
    providerId: string;
    model: string;
    report: InteractiveInterviewReport;
  }) => Promise<{ saved: boolean; report_path?: string } | null>;
  resolveProviderEnvOverrides?: (providerId: string) => Promise<Record<string, string> | null>;
  onAddProvider?: (providerId: string, provider: ProviderConfig) => void;
  onUpdateProvider?: (providerId: string, updates: Partial<ProviderConfig>) => void;
  onDeleteProvider?: (providerId: string) => void | Promise<void>;
  onUpdateConfig?: (config: LlmConfig) => void;
  onTestProvider?: (provider: SimpleProvider, onEvent?: (event: TestEvent) => void) => Promise<TestResult | null>;
  onCancelTestProvider?: () => void;
  onCancelInterview?: () => void;
}

// ============================================================================
// Helper Functions
// ============================================================================

function buildSimpleProvider(
  providerId: string,
  provider: ProviderConfig,
  roles?: Record<string, { provider_id?: string; model?: string }>
): SimpleProvider {
  const kind = (provider.type || PROVIDER_KINDS.OPENAI_COMPAT) as ProviderKind;
  const isCli = isCLIProviderType(provider.type) || Boolean(provider.command);
  
  const conn = isCli
    ? {
        kind: kind === PROVIDER_KINDS.GEMINI_CLI ? 'gemini_cli' : 'codex_cli' as const,
        command: provider.command || (kind === PROVIDER_KINDS.GEMINI_CLI ? 'gemini' : 'codex'),
        args: provider.args || [],
        env: provider.env || {},
      }
    : {
        kind: 'http' as const,
        baseUrl: provider.base_url || '',
        apiKey: provider.api_key,
      };

  // 解析模型
  let modelId = '';
  if (typeof provider.model === 'string' && provider.model.trim()) {
    modelId = provider.model.trim();
  } else if (typeof provider.default_model === 'string' && provider.default_model.trim()) {
    modelId = provider.default_model.trim();
  }
  
  if (!modelId && roles) {
    for (const roleCfg of Object.values(roles)) {
      if (roleCfg?.provider_id === providerId && roleCfg.model) {
        modelId = roleCfg.model;
        break;
      }
    }
  }

  return {
    id: providerId,
    name: provider.name || providerId,
    kind,
    conn,
    cliMode: provider.cli_mode,
    modelId,
    status: 'untested',
  };
}

function resolveModelForSelection(
  roleId: RoleId,
  providerId: string,
  config: LlmConfig | null
): string {
  if (!config) {
    console.log('[resolveModelForSelection] config is null');
    return '';
  }
  
  const providerCfg = config.providers?.[providerId];
  const roleCfg = config.roles?.[roleId];
  
  console.log('[resolveModelForSelection]', {
    roleId,
    providerId,
    providerCfg: providerCfg ? {
      model: providerCfg.model,
      model_id: providerCfg.model_id,
      default_model: providerCfg.default_model,
      type: providerCfg.type,
    } : null,
    roleCfg: roleCfg ? { provider_id: roleCfg.provider_id, model: roleCfg.model } : null,
  });
  
  // 检查多个可能的model字段（与原始版本保持一致）
  if (providerCfg?.model) {
    console.log('[resolveModelForSelection] using providerCfg.model:', providerCfg.model);
    return providerCfg.model;
  }
  if (providerCfg?.model_id) {
    console.log('[resolveModelForSelection] using providerCfg.model_id:', providerCfg.model_id);
    return providerCfg.model_id;
  }
  if (providerCfg?.default_model) {
    console.log('[resolveModelForSelection] using providerCfg.default_model:', providerCfg.default_model);
    return providerCfg.default_model;
  }
  if (roleCfg?.provider_id === providerId && roleCfg.model) {
    console.log('[resolveModelForSelection] using roleCfg.model:', roleCfg.model);
    return roleCfg.model;
  }
  
  console.log('[resolveModelForSelection] no model found, returning empty string');
  return '';
}

// ============================================================================
// Navigation Component
// ============================================================================

function TabNavigation({ 
  globalReadiness 
}: { 
  globalReadiness: { state: string; color: string } 
}) {
  const { state, switchTab } = useProviderContext();
  const { activeTab } = state;

  return (
    <div className="rounded-2xl border border-cyan-500/20 bg-[radial-gradient(circle_at_top,_rgba(14,116,144,0.22),_transparent_60%)] p-4 shadow-[0_0_30px_rgba(34,211,238,0.2)]">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <button
            onClick={() => switchTab('config')}
            className={`px-4 py-2 text-[11px] font-semibold uppercase tracking-wider rounded-lg border transition-all ${
              activeTab === 'config'
                ? 'bg-cyan-500/20 text-cyan-200 border-cyan-400/40 shadow-[0_0_16px_rgba(34,211,238,0.25)]'
                : 'text-text-dim border-white/10 hover:border-cyan-400/40 hover:text-cyan-100'
            }`}
          >
            CONFIG
          </button>
          <button
            type="button"
            onClick={() => switchTab('deepTest')}
            className={`px-4 py-2 text-[11px] font-semibold uppercase tracking-wider rounded-lg border transition-all ${
              activeTab === 'deepTest'
                ? 'bg-emerald-500/20 text-emerald-200 border-emerald-400/40 shadow-[0_0_16px_rgba(16,185,129,0.25)]'
                : 'text-text-dim border-white/10 hover:border-emerald-400/40 hover:text-emerald-100'
            }`}
          >
            DEEP TEST
          </button>
        </div>

        <div className="flex items-center gap-2">
          {globalReadiness.state === 'READY' ? (
            <CheckCircle2 className="size-4 text-emerald-400" />
          ) : (
            <AlertTriangle className="size-4 text-yellow-400" />
          )}
          <span className="text-[10px] uppercase tracking-wider px-2 py-1 rounded border border-white/10 bg-black/40">
            {globalReadiness.state}
          </span>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Deep Test Panel
// ============================================================================

function DeepTestPanel({
  llmConfig,
  llmStatus,
  onRunConnectivityTest,
  onRunInterview,
  onAskInteractiveInterview,
  onSaveInteractiveInterview,
  resolveProviderEnvOverrides,
  onCancelInterview,
}: {
  llmConfig: LlmConfig | null;
  llmStatus: LlmStatus | null;
  onRunConnectivityTest: (role: RoleId, providerId: string, model: string) => Promise<Record<string, unknown> | null>;
  onRunInterview: (role: RoleId, providerId: string, model: string, onEvent?: (event: TestEvent) => void) => Promise<Record<string, unknown> | null>;
  onAskInteractiveInterview: LLMSettingsTabProps['onAskInteractiveInterview'];
  onSaveInteractiveInterview: LLMSettingsTabProps['onSaveInteractiveInterview'];
  resolveProviderEnvOverrides?: (providerId: string) => Promise<Record<string, string> | null>;
  onCancelInterview?: () => void;
}) {
  const { state, setInterviewMode, setDeepView, selectRole, selectProvider } = useProviderContext();
  const { interviewMode, deepView, interviewPanel, interviewRunning, connectivityRunning, connectivityRunningKey } = state;
  const selectedRole = useSelectedRole();
  const { buildProviderSummaries, buildConnectivityMap, getRoleProviderConnectivity } = useConnectivityStore();

  const providers = useMemo(() => {
    if (!llmConfig?.providers) return [];
    return buildProviderSummaries(llmConfig.providers);
  }, [llmConfig?.providers, buildProviderSummaries]);

  const connectivityResults = useMemo(() => {
    return buildConnectivityMap();
  }, [buildConnectivityMap]);

  const selectedProviderId = state.selectedProviderId;

  // 简化的角色配置
  const roles = useMemo(() => {
    const roleIds: RoleId[] = ['pm', 'director', 'qa', 'docs'];
    const roleMeta: Record<RoleId, { label: string; description: string }> = {
      pm: { label: 'PM 项目经理', description: '负责项目管理、任务规划和进度跟踪' },
      director: { label: 'Director 导演', description: '负责代码执行、技术实现和系统架构' },
      qa: { label: 'QA 质量保证', description: '负责代码审查、测试和质量控制' },
      docs: { label: 'Docs 文档', description: '负责文档生成和维护' },
    };
    
    return roleIds.map((roleId) => {
      const roleCfg = llmConfig?.roles?.[roleId];
      const status = llmStatus?.roles?.[roleId];
      
      return {
        id: roleId,
        label: roleMeta[roleId].label,
        description: roleMeta[roleId].description,
        requiresThinking: roleId === 'pm' || roleId === 'director',
        minConfidence: 0.5,
        candidate: {
          providerId: roleCfg?.provider_id || '',
          providerName: roleCfg?.provider_id 
            ? (llmConfig?.providers?.[roleCfg.provider_id]?.name || roleCfg.provider_id)
            : 'Unassigned',
          model: roleCfg?.model || '',
        },
        readiness: {
          ready: status?.ready,
          grade: status?.grade,
        },
      };
    });
  }, [llmConfig, llmStatus]);

  const selectedMeta = roles.find((r) => r.id === selectedRole);

  const handleRunConnectivity = useCallback(async (roleId: RoleId, providerId: string) => {
    const model = resolveModelForSelection(roleId, providerId, llmConfig);
    if (!model) return;
    await onRunConnectivityTest(roleId, providerId, model);
  }, [llmConfig, onRunConnectivityTest]);

  const handleStartInterview = useCallback(async (roleId: RoleId, providerId: string) => {
    const model = resolveModelForSelection(roleId, providerId, llmConfig);
    if (!model) return;
    await onRunInterview(roleId, providerId, model);
  }, [llmConfig, onRunInterview]);

  return (
    <div className="flex flex-col gap-4 w-full flex-1 min-h-0">
      <div className="rounded-2xl border border-emerald-500/20 bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.22),_transparent_60%)] p-4 shadow-[0_0_30px_rgba(16,185,129,0.18)]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-widest text-emerald-200">Deep Test Chamber</div>
            <div className="text-[10px] text-text-dim mt-1">
              深度测试用于验证角色与模型适配度，输出详细能力报告。
            </div>
          </div>
          <div className="flex items-center gap-1 rounded-lg border border-white/10 bg-black/40 p-1">
            <button
              onClick={() => setInterviewMode('interactive')}
              className={`px-3 py-1.5 text-[10px] font-semibold rounded transition-all ${
                interviewMode === 'interactive'
                  ? 'bg-emerald-500/20 text-emerald-200'
                  : 'text-text-dim hover:text-emerald-100'
              }`}
            >
              INTERACTIVE
            </button>
            <button
              onClick={() => {
                setInterviewMode('auto');
                setDeepView('hall');
              }}
              className={`px-3 py-1.5 text-[10px] font-semibold rounded transition-all ${
                interviewMode === 'auto'
                  ? 'bg-cyan-500/20 text-cyan-200'
                  : 'text-text-dim hover:text-cyan-100'
              }`}
            >
              AUTO
            </button>
          </div>
        </div>
      </div>

      <div className="w-full flex-1 min-h-0">
        {interviewMode === 'interactive' ? (
          <InteractiveInterviewHall
            roles={roles}
            providers={providers}
            selectedRole={selectedRole}
            selectedProvider={selectedProviderId}
            selectedModel={llmConfig?.roles?.[selectedRole]?.model || ''}
            onSelectRole={selectRole}
            onSelectProvider={selectProvider}
            onAskQuestion={onAskInteractiveInterview}
            onSaveReport={onSaveInteractiveInterview}
            resolveEnvOverrides={resolveProviderEnvOverrides}
          />
        ) : deepView === 'hall' ? (
          <InterviewHall
            roles={roles}
            selectedRole={selectedRole}
            providers={providers}
            selectedProvider={selectedProviderId}
            onSelectRole={selectRole}
            onSelectProvider={selectProvider}
            onRunConnectivityTest={handleRunConnectivity}
            onRunInterview={handleStartInterview}
            connectivityResults={connectivityResults}
            interviewRunning={interviewRunning}
            connectivityRunning={connectivityRunning}
            onSkipConnectivityTest={() => {}}
          />
        ) : (
          <InterviewSession
            roleLabel={selectedMeta?.label || selectedRole}
            roleId={selectedRole}
            report={interviewPanel.report || null}
            running={interviewRunning}
            error={interviewPanel.error}
            onBack={() => setDeepView('hall')}
          />
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

function LLMSettingsTabInner({
  llmConfig,
  llmStatus,
  llmLoading,
  llmSaving,
  llmError,
  deletingProviders,
  onSaveConfig,
  onRunInterview,
  onRunConnectivityTest,
  onAskInteractiveInterview,
  onSaveInteractiveInterview,
  resolveProviderEnvOverrides,
  onAddProvider,
  onUpdateProvider,
  onDeleteProvider,
  onUpdateConfig,
  onTestProvider,
  onCancelTestProvider,
  onCancelInterview,
}: LLMSettingsTabProps) {
  const { state, switchTab, startTest, completeTest, closeTestPanel, setConfigView } = useProviderContext();
  const { activeTab, configView, testPanel } = state;
  
  const { events, addEvent, resetEvents } = useTestEvents();
  const panelHostRef = useRef<HTMLElement | null>(null);

  // 初始化 portal host
  useEffect(() => {
    if (typeof document !== 'undefined') {
      panelHostRef.current = document.getElementById('llm-test-panel-slot');
    }
  }, []);

  // Provider Registry
  const {
    loading: providersLoading,
    error: providersError,
    providers,
    getProviderInfo,
    getProviderDefaultConfig,
    getProviderComponent,
    getCostClass,
  } = useProviderRegistry();

  // Global readiness
  const globalReadiness = useMemo(() => {
    const s = llmStatus?.state || 'UNKNOWN';
    if (s === 'READY') return { state: 'READY', color: 'text-emerald-400' };
    if (s === 'BLOCKED') return { state: 'BLOCKED', color: 'text-amber-400' };
    return { state: 'UNKNOWN', color: 'text-gray-400' };
  }, [llmStatus]);

  // Visual config
  const visualConfig = useMemo(() => {
    if (!llmConfig) return null;
    return {
      providers: llmConfig.providers || {},
      roles: llmConfig.roles || {},
      visual_layout: (llmConfig as unknown as Record<string, unknown>).visual_layout as Record<string, { x: number; y: number }> || {},
      policies: llmConfig.policies,
    } as VisualGraphConfig;
  }, [llmConfig]);

  const visualStatus = useMemo(() => {
    if (!llmStatus) return null;
    const rolesStatus: Record<string, { ready?: boolean; grade?: string }> = {};
    Object.entries(llmStatus.roles || {}).forEach(([roleId, role]) => {
      rolesStatus[roleId] = { ready: role.ready, grade: role.grade };
    });
    return { roles: rolesStatus } as VisualGraphStatus;
  }, [llmStatus]);

  // Test handlers
  const handleTestProvider = useCallback(async (providerId: string) => {
    if (!onTestProvider || !llmConfig) return;
    
    const cfg = llmConfig.providers?.[providerId];
    if (!cfg) return;

    const simpleProvider = buildSimpleProvider(providerId, cfg, llmConfig.roles);
    
    startTest(providerId);
    resetEvents();
    
    try {
      const result = await onTestProvider(simpleProvider, (event) => {
        addEvent(event);
      });
      completeTest(providerId, result?.ready ?? false);
    } catch {
      completeTest(providerId, false);
    }
  }, [llmConfig, onTestProvider, startTest, completeTest, addEvent, resetEvents]);

  // Handle visual config change
  const handleVisualConfigChange = useCallback((nextConfig: VisualGraphConfig) => {
    if (!onUpdateConfig || !llmConfig) return;
    
    onUpdateConfig({
      ...llmConfig,
      visual_layout: nextConfig.visual_layout,
      visual_node_states: (nextConfig as unknown as Record<string, unknown>).visual_node_states,
      visual_viewport: (nextConfig as unknown as Record<string, unknown>).visual_viewport,
    });
  }, [llmConfig, onUpdateConfig]);

  // Loading state
  if (llmLoading || providersLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex items-center gap-2 text-text-muted">
          <Loader2 className="size-4 animate-spin" />
          <span className="text-sm">Loading LLM configuration...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 h-full min-h-0">
      <TabNavigation globalReadiness={globalReadiness} />

      {(llmError || providersError) && (
        <div className="text-xs text-status-error bg-status-error/10 border border-status-error/20 rounded p-2">
          {llmError || providersError}
        </div>
      )}

      {llmSaving && (
        <div className="flex items-center gap-2 text-[10px] text-text-dim">
          <Loader2 className="size-3 animate-spin" />
          <span>Saving LLM configuration...</span>
        </div>
      )}

      {activeTab === 'config' && (
        <div className="space-y-4">
          {/* View Switcher */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-text-main mb-1">LLM 提供商配置</h3>
              <p className="text-[10px] text-text-dim">
                列表视图用于日常配置，视觉视图用于角色-模型连线。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-1 rounded-lg border border-cyan-500/20 bg-black/40 p-1">
                <button
                  onClick={() => setConfigView('list')}
                  className={`px-3 py-1.5 text-[10px] font-semibold rounded transition-all ${
                    configView === 'list'
                      ? 'bg-cyan-500/20 text-cyan-200'
                      : 'text-text-dim hover:text-cyan-100'
                  }`}
                >
                  列表视图
                </button>
                <button
                  onClick={() => setConfigView('visual')}
                  className={`px-3 py-1.5 text-[10px] font-semibold rounded transition-all ${
                    configView === 'visual'
                      ? 'bg-fuchsia-500/20 text-fuchsia-200'
                      : 'text-text-dim hover:text-fuchsia-100'
                  }`}
                >
                  视觉视图
                </button>
              </div>
            </div>
          </div>

          {configView === 'visual' ? (
            <LLMVisualEditor
              config={visualConfig}
              status={visualStatus}
              onConfigChange={handleVisualConfigChange}
              onSave={onSaveConfig}
            />
          ) : (
            <ProviderListManager
              providers={providers}
              configuredProviders={llmConfig?.providers || {}}
              llmStatus={llmStatus}
              isSaving={llmSaving}
              deletingProviders={deletingProviders}
              getProviderInfo={(type) => getProviderInfo(type)}
              getProviderComponent={getProviderComponent}
              getCostClass={getCostClass}
              onAddProvider={onAddProvider || (() => {})}
              onUpdateProvider={onUpdateProvider || (() => {})}
              onDeleteProvider={onDeleteProvider || (() => {})}
              onTestProvider={handleTestProvider}
              onEnterDeepTest={() => switchTab('deepTest')}
            />
          )}
        </div>
      )}

      {activeTab === 'deepTest' && (
        <DeepTestPanel
          llmConfig={llmConfig}
          llmStatus={llmStatus}
          onRunConnectivityTest={onRunConnectivityTest}
          onRunInterview={onRunInterview}
          onAskInteractiveInterview={onAskInteractiveInterview}
          onSaveInteractiveInterview={onSaveInteractiveInterview}
          resolveProviderEnvOverrides={resolveProviderEnvOverrides}
          onCancelInterview={onCancelInterview}
        />
      )}

      {/* Test Panel Portal */}
      {panelHostRef.current && testPanel.selectedProviderId && activeTab === 'config' && (
        createPortal(
          <TestPanel
            provider={buildSimpleProvider(
              testPanel.selectedProviderId,
              llmConfig?.providers?.[testPanel.selectedProviderId] || {},
              llmConfig?.roles
            )}
            events={events}
            status={testPanel.status}
            onClose={closeTestPanel}
            onCancel={onCancelTestProvider || (() => {})}
          />,
          panelHostRef.current
        )
      )}
    </div>
  );
}

// ============================================================================
// Exported Component with Provider
// ============================================================================

export function LLMSettingsTab(props: LLMSettingsTabProps) {
  return (
    <ProviderContextProvider>
      <LLMSettingsTabInner {...props} />
    </ProviderContextProvider>
  );
}

export default LLMSettingsTab;
