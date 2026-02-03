import { Loader2, CheckCircle2, AlertTriangle, Plus, Settings, PlayCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { InterviewHall } from './interview/InterviewHall';
import { InterviewSession } from './interview/InterviewSession';
import { SimpleModelCard, type SimpleProvider } from './SimpleModelCard';
import { TestPanel } from './test/TestPanel';
import { useTestEvents } from './test/hooks/useTestEvents';
import type { TestEvent, TestResult } from './test/types';
import { LLMVisualEditor } from './visual/LLMVisualEditor';
import { CodexModelBrowser } from './model-browser/CodexModelBrowser';
import { isCLIConnection } from './types';

interface LlmProviderConfig {
  type?: string;
  name?: string;
  command?: string;
  args?: string[];
  cli_mode?: 'tui' | 'headless';
  codex_exec?: Record<string, unknown>;
  env?: Record<string, string>;
  base_url?: string;
  api_key_ref?: string;
  list_args?: string[];
  tui_args?: string[];
  output_path?: string;
  timeout?: number;
  retries?: number;
  api_path?: string;
  models_path?: string;
  headers?: Record<string, string>;
  temperature?: number;
}

interface LlmRoleConfig {
  provider_id?: string;
  model?: string;
  profile?: string;
}

interface RoleRequirement {
  requires_thinking?: boolean;
  min_confidence?: number;
  error_message?: string;
}

interface LlmConfig {
  schema_version: number;
  providers: Record<string, LlmProviderConfig>;
  roles: Record<string, LlmRoleConfig>;
  policies?: {
    required_ready_roles?: string[];
    test_required_suites?: string[];
    role_requirements?: Record<string, RoleRequirement>;
  };
}

interface LlmStatusRole {
  provider_id?: string;
  model?: string;
  profile?: string;
  ready?: boolean;
  grade?: string;
  last_run_id?: string | null;
  timestamp?: string | null;
  suites?: Record<string, unknown> | null;
  runtime_supported?: boolean;
}

interface LlmStatus {
  state: string;
  required_ready_roles: string[];
  blocked_roles: string[];
  unsupported_roles: string[];
  roles: Record<string, LlmStatusRole>;
}

type RoleId = 'pm' | 'director' | 'qa' | 'docs';

interface InterviewSuiteReport {
  status?: string;
  final_score?: number;
  thinking?: {
    supports_thinking?: boolean;
    confidence?: number;
    format?: string;
    thinking_text?: string;
  };
  cases?: Array<Record<string, unknown>>;
  details?: {
    recommendation?: string;
    reason?: string;
    threshold?: number;
  };
}

interface LLMSettingsTabProps {
  llmConfig: LlmConfig | null;
  llmStatus: LlmStatus | null;
  llmLoading: boolean;
  llmSaving: boolean;
  llmError: string | null;
  onSaveConfig: () => void;
  onRunInterview: (role: RoleId) => Promise<Record<string, unknown> | null>;
  onRunReadiness: (role: RoleId) => Promise<Record<string, unknown> | null>;
  onAddProvider?: (provider: SimpleProvider) => void;
  onUpdateProvider?: (id: string, updates: Partial<SimpleProvider>) => void;
  onDeleteProvider?: (id: string) => void;
  onUpdateConfig?: (config: LlmConfig) => void;
  onTestProvider?: (
    provider: SimpleProvider,
    onEvent?: (event: TestEvent) => void
  ) => Promise<TestResult | null>;
  onCancelTestProvider?: () => void;
}

const ROLE_META: Record<RoleId, { label: string; description: string; badge: string }> = {
  pm: {
    label: 'PM 项目经理',
    description: '负责项目管理、任务规划和进度跟踪',
    badge: 'bg-cyan-500/20 text-cyan-200 border-cyan-500/30'
  },
  director: {
    label: 'Director 导演',
    description: '负责代码执行、技术实现和系统架构',
    badge: 'bg-emerald-500/20 text-emerald-200 border-emerald-500/30'
  },
  qa: {
    label: 'QA 质量保证',
    description: '负责代码审查、测试和质量控制',
    badge: 'bg-blue-500/20 text-blue-200 border-blue-500/30'
  },
  docs: {
    label: 'Docs 文档',
    description: '负责文档生成和维护',
    badge: 'bg-amber-500/20 text-amber-200 border-amber-500/30'
  }
};

const DEFAULT_ROLE_REQUIREMENTS: Record<RoleId, RoleRequirement> = {
  pm: {
    requires_thinking: true,
    min_confidence: 0.7,
    error_message: 'PM 角色需要支持思考功能的LLM模型'
  },
  director: {
    requires_thinking: true,
    min_confidence: 0.7,
    error_message: 'Director 角色需要支持思考功能的LLM模型'
  },
  qa: {
    requires_thinking: false,
    min_confidence: 0.5,
    error_message: 'QA 角色需要可用的LLM模型'
  },
  docs: {
    requires_thinking: false,
    min_confidence: 0.5,
    error_message: 'Docs 角色需要可用的LLM模型'
  }
};

const CODEX_CLI_ARGS = [
  'exec',
  '--skip-git-repo-check',
  '--color',
  'never',
  '--model',
  '{model}',
  '--sandbox',
  'danger-full-access',
  '--json',
  '{prompt}',
];

const createCodexProvider = (): SimpleProvider => ({
  id: `codex-cli-${Date.now()}`,
  name: 'Codex CLI',
  kind: 'codex_cli',
  conn: { kind: 'codex_cli', command: 'codex', args: CODEX_CLI_ARGS },
  cliMode: 'headless',
  modelId: 'gpt-5.2-codex',
  status: 'untested',
  costClass: 'FIXED',
});


function extractThinkingMeta(suites?: Record<string, unknown> | null) {
  if (!suites || typeof suites !== 'object') return null;
  const suite = (suites as Record<string, unknown>).thinking as Record<string, unknown> | undefined;
  if (!suite) return null;
  const details = suite.details as Record<string, unknown> | undefined;
  const thinking = (details?.thinking as Record<string, unknown>) || (suite.thinking as Record<string, unknown>);
  if (!thinking) return null;
  return {
    supportsThinking: Boolean(thinking.supports_thinking),
    confidence:
      typeof thinking.confidence === 'number'
        ? thinking.confidence
        : thinking.confidence
          ? Number(thinking.confidence)
          : null,
    format: typeof thinking.format === 'string' ? thinking.format : null,
    thinkingText: typeof thinking.thinking_text === 'string' ? thinking.thinking_text : null
  };
}

function buildRoleRequirements(config: LlmConfig | null): Record<RoleId, RoleRequirement> {
  const policies = config?.policies?.role_requirements || {};
  return {
    pm: { ...DEFAULT_ROLE_REQUIREMENTS.pm, ...(policies.pm || {}) },
    director: { ...DEFAULT_ROLE_REQUIREMENTS.director, ...(policies.director || {}) },
    qa: { ...DEFAULT_ROLE_REQUIREMENTS.qa, ...(policies.qa || {}) },
    docs: { ...DEFAULT_ROLE_REQUIREMENTS.docs, ...(policies.docs || {}) }
  };
}

export function LLMSettingsTab({
  llmConfig,
  llmStatus,
  llmLoading,
  llmSaving,
  llmError,
  onSaveConfig,
  onRunInterview,
  onRunReadiness,
  onAddProvider,
  onUpdateProvider,
  onDeleteProvider,
  onUpdateConfig,
  onTestProvider,
  onCancelTestProvider
}: LLMSettingsTabProps) {
  const [selectedRole, setSelectedRole] = useState<RoleId>('pm');
  const [view, setView] = useState<'config' | 'hall' | 'session'>('config');
  const [configView, setConfigView] = useState<'list' | 'visual'>('list');
  const [interviewReport, setInterviewReport] = useState<InterviewSuiteReport | null>(null);
  const [interviewError, setInterviewError] = useState<string | null>(null);
  const [interviewRunning, setInterviewRunning] = useState(false);
  const [readinessRunning, setReadinessRunning] = useState(false);
  const [providers, setProviders] = useState<SimpleProvider[]>([]);
  const [selectedTestProviderId, setSelectedTestProviderId] = useState<string | null>(null);
  const [testStatus, setTestStatus] = useState<'idle' | 'running' | 'success' | 'failed'>('idle');
  const [testCancelled, setTestCancelled] = useState(false);
  const { events, addEvent, resetEvents } = useTestEvents();
  const [panelHost, setPanelHost] = useState<HTMLElement | null>(null);

  const updateProviderState = (id: string, updates: Partial<SimpleProvider>) => {
    setProviders((prev) => prev.map((provider) => (provider.id === id ? { ...provider, ...updates } : provider)));
  };

  const selectedTestProvider = useMemo(
    () => providers.find((provider) => provider.id === selectedTestProviderId) || null,
    [providers, selectedTestProviderId]
  );

  const openTestPanel = (providerId: string) => {
    setSelectedTestProviderId(providerId);
    setTestStatus('idle');
    setTestCancelled(false);
    resetEvents();
  };

  const closeTestPanel = () => {
    setSelectedTestProviderId(null);
    setTestStatus('idle');
    setTestCancelled(false);
    resetEvents();
  };

  const cancelTestRun = () => {
    if (onCancelTestProvider) {
      onCancelTestProvider();
    }
    setTestCancelled(true);
    addEvent({
      type: 'error',
      timestamp: new Date().toISOString(),
      content: 'Test cancelled by user'
    });
    setTestStatus('failed');
  };

  const shouldSkipErrorEvent = (err: unknown): boolean => {
    if (!err || typeof err !== 'object') return false;
    return 'skipUiEvent' in err && Boolean((err as { skipUiEvent?: boolean }).skipUiEvent);
  };

  const runSelectedTest = async () => {
    if (!selectedTestProvider || !onTestProvider) return;
    setTestStatus('running');
    setTestCancelled(false);
    resetEvents();
    addEvent({
      type: 'command',
      timestamp: new Date().toISOString(),
      content: `Preparing test for ${selectedTestProvider.name}`
    });
    updateProviderState(selectedTestProvider.id, { status: 'testing', lastError: undefined });
    try {
      const result = await onTestProvider(selectedTestProvider, (event) => {
        addEvent(event);
      });
      if (!result) {
        setTestStatus('failed');
        const hasErrorEvent = events.some((event) => event.type === 'error');
        const fallbackMessage = testCancelled ? '测试已取消' : '测试未返回结果';
        if (!hasErrorEvent) {
          addEvent({
            type: 'error',
            timestamp: new Date().toISOString(),
            content: fallbackMessage
          });
        }
        updateProviderState(selectedTestProvider.id, {
          status: 'failed',
          lastError: testCancelled ? '测试已取消' : '测试未返回结果',
          lastTest: {
            at: new Date().toISOString(),
            note: testCancelled ? '测试已取消' : '测试未返回结果'
          }
        });
        return;
      }
      const ready = result.ready ?? result.grade === 'PASS';
      setTestStatus(ready ? 'success' : 'failed');
      updateProviderState(selectedTestProvider.id, {
        status: ready ? 'ready' : 'failed',
        lastError: ready ? undefined : '测试未通过',
        lastTest: {
          at: new Date().toISOString(),
          latencyMs: typeof result.latencyMs === 'number' ? Math.round(result.latencyMs) : undefined,
          usage: {
            totalTokens: result.usage?.totalTokens,
            estimated: result.usage?.estimated
          },
          note: ready ? '测试通过' : '测试未通过'
        }
      });
      addEvent({
        type: ready ? 'result' : 'error',
        timestamp: new Date().toISOString(),
        content: ready ? '测试完成' : '测试未通过'
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : '测试失败';
      setTestStatus('failed');
      if (!shouldSkipErrorEvent(err)) {
        addEvent({
          type: 'error',
          timestamp: new Date().toISOString(),
          content: message
        });
      }
      updateProviderState(selectedTestProvider.id, {
        status: 'failed',
        lastError: message,
        lastTest: {
          at: new Date().toISOString(),
          note: '测试失败'
        }
      });
    }
  };

  const roleRequirements = useMemo(() => buildRoleRequirements(llmConfig), [llmConfig]);

  const roles = useMemo(() => {
    const roleIds: RoleId[] = ['pm', 'director', 'qa', 'docs'];
    return roleIds.map((roleId) => {
      const roleCfg = llmConfig?.roles?.[roleId];
      const providerId = roleCfg?.provider_id || '';
      const providerCfg = providerId ? llmConfig?.providers?.[providerId] : undefined;
      const status = llmStatus?.roles?.[roleId];
      const thinkingMeta = extractThinkingMeta(status?.suites || null);
      const requirement = roleRequirements[roleId];
      return {
        id: roleId,
        label: ROLE_META[roleId].label,
        description: ROLE_META[roleId].description,
        requiresThinking: Boolean(requirement?.requires_thinking),
        minConfidence: requirement?.min_confidence ?? 0.5,
        thinkingConfidence: thinkingMeta?.confidence ?? null,
        thinkingSupported: thinkingMeta?.supportsThinking ?? null,
        candidate: {
          providerId,
          providerName: providerCfg?.name || providerId || 'Unassigned',
          model: roleCfg?.model || ''
        },
        readiness: {
          ready: status?.ready,
          grade: status?.grade
        }
      };
    });
  }, [llmConfig, llmStatus, roleRequirements]);

  const candidates = useMemo(() => {
    return roles
      .filter((role) => role.candidate?.model)
      .map((role) => ({
        id: `${role.id}-${role.candidate?.providerId || 'unknown'}-${role.candidate?.model || 'model'}`,
        roleLabel: role.label,
        providerName: role.candidate?.providerName || 'Unknown',
        model: role.candidate?.model || 'Unassigned',
        ready: role.readiness?.ready,
        thinkingSupported: role.thinkingSupported ?? null,
        thinkingConfidence: role.thinkingConfidence ?? null
      }));
  }, [roles]);

  useEffect(() => {
    if (!llmConfig) return;
    if (!roles.find((role) => role.id === selectedRole)) {
      setSelectedRole('pm');
    }
  }, [llmConfig, roles, selectedRole]);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    setPanelHost(document.getElementById('llm-test-panel-slot'));
  }, []);

  useEffect(() => {
    if (!selectedTestProviderId) return;
    if (!providers.find((provider) => provider.id === selectedTestProviderId)) {
      closeTestPanel();
    }
  }, [providers, selectedTestProviderId]);

  useEffect(() => {
    if (view !== 'config' && selectedTestProviderId) {
      closeTestPanel();
    }
  }, [view, selectedTestProviderId]);

  const globalReadiness = useMemo(() => {
    const state = llmStatus?.state || 'UNKNOWN';
    if (state === 'READY') {
      return { state: 'READY', color: 'text-emerald-400' };
    }
    if (state === 'BLOCKED') {
      return { state: 'BLOCKED', color: 'text-amber-400' };
    }
    return { state: 'UNKNOWN', color: 'text-gray-400' };
  }, [llmStatus?.state]);

  const selectedMeta = roles.find((role) => role.id === selectedRole);
  const canRunReadiness = Boolean(
    selectedMeta?.candidate?.providerId && selectedMeta?.candidate?.model
  );
  let disabledReason: string | null = null;
  if (!selectedMeta?.candidate?.providerId || !selectedMeta?.candidate?.model) {
    disabledReason = '请选择LLM提供商和模型';
  } else if (selectedMeta.requiresThinking) {
    const confidence = selectedMeta.thinkingConfidence;
    if (confidence !== null && confidence < selectedMeta.minConfidence) {
      disabledReason =
        roleRequirements[selectedRole]?.error_message ||
        'Thinking 功能置信度不足';
    }
  }

  const handleStartInterview = async () => {
    if (!selectedMeta) return;
    setInterviewError(null);
    setInterviewReport(null);
    setInterviewRunning(true);
    setView('session');
    try {
      const report = await onRunInterview(selectedMeta.id);
      const suiteReport = (report?.suites as Record<string, unknown> | undefined)?.interview;
      if (suiteReport && typeof suiteReport === 'object') {
        setInterviewReport(suiteReport as InterviewSuiteReport);
      } else if (report && typeof report === 'object') {
        setInterviewReport(report as InterviewSuiteReport);
      } else {
        setInterviewReport(null);
      }
    } catch (error) {
      setInterviewError(error instanceof Error ? error.message : 'Interview failed');
    } finally {
      setInterviewRunning(false);
    }
  };

  const handleRunReadiness = async () => {
    if (!selectedMeta) return;
    setReadinessRunning(true);
    try {
      await onRunReadiness(selectedMeta.id);
    } finally {
      setReadinessRunning(false);
    }
  };

  if (llmLoading) {
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
    <div className="space-y-6">
      {/* 步骤导航 */}
      <div className="bg-white/5 rounded-xl p-4 border border-white/5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setView('config')}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                view === 'config' 
                  ? 'bg-accent/20 text-accent border border-accent/30' 
                  : 'text-text-dim hover:text-text-main hover:bg-white/5'
              }`}
            >
              <Settings className="size-4" />
              1. 配置LLM
            </button>
            <button
              onClick={() => setView('hall')}
              disabled={providers.length === 0}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                view === 'hall' 
                  ? 'bg-accent/20 text-accent border border-accent/30' 
                  : providers.length === 0
                    ? 'text-gray-500 cursor-not-allowed'
                    : 'text-text-dim hover:text-text-main hover:bg-white/5'
              }`}
            >
              <PlayCircle className="size-4" />
              2. 测试模型
            </button>
          </div>
          
          <div className="flex items-center gap-2">
            {globalReadiness.state === 'READY' ? (
              <CheckCircle2 className="size-4 text-emerald-400" />
            ) : (
              <AlertTriangle className="size-4 text-yellow-400" />
            )}
            <span className="text-[10px] uppercase tracking-wider px-2 py-1 rounded border border-white/10 bg-black/30">
              {globalReadiness.state}
            </span>
          </div>
        </div>

        {llmError ? (
          <div className="mt-3 text-xs text-status-error bg-status-error/10 border border-status-error/20 rounded p-2">
            {llmError}
          </div>
        ) : null}
      </div>

      {/* 配置视图 */}
      {view === 'config' && (
        <div className="space-y-4">
          {providers.length === 0 ? (
            <>
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-text-main mb-1">LLM 提供商配置</h3>
                  <p className="text-[10px] text-text-dim">
                    添加和配置LLM提供商（OpenAI、Ollama、Claude等）
                  </p>
                </div>
                <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-black/30 p-1">
                  <button
                    type="button"
                    onClick={() => setConfigView('list')}
                    className={`px-3 py-1 text-[10px] font-semibold rounded ${
                      configView === 'list' ? 'bg-cyan-500/70 text-white' : 'text-text-dim hover:text-text-main'
                    }`}
                  >
                    列表
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfigView('visual')}
                    className={`px-3 py-1 text-[10px] font-semibold rounded ${
                      configView === 'visual' ? 'bg-fuchsia-500/70 text-white' : 'text-text-dim hover:text-text-main'
                    }`}
                  >
                    视觉
                  </button>
                </div>
              </div>
              {configView === 'visual' ? (
                <LLMVisualEditor
                  config={llmConfig}
                  status={llmStatus}
                  onConfigChange={onUpdateConfig}
                  onSave={onSaveConfig}
                />
              ) : (
                <div className="bg-white/5 rounded-xl p-8 border border-white/5 text-center">
                  <Settings className="size-8 text-text-dim mx-auto mb-3" />
                  <h4 className="text-sm font-medium text-text-main mb-2">尚未配置LLM提供商</h4>
                  <p className="text-xs text-text-dim mb-4">
                    请先添加至少一个LLM提供商，然后进行模型测试
                  </p>
                  <div className="flex items-center justify-center gap-3 flex-wrap">
                    <button
                      onClick={() => {
                        const newProvider = createCodexProvider();
                        setProviders([...providers, newProvider]);
                        onAddProvider?.(newProvider);
                      }}
                      className="px-4 py-2 text-xs font-semibold bg-emerald-500/70 hover:bg-emerald-500 text-white rounded transition-colors"
                    >
                      添加 Codex CLI
                    </button>
                    <button
                      onClick={() => {
                        const newProvider: SimpleProvider = {
                          id: `provider-${Date.now()}`,
                          name: 'OpenAI',
                          kind: 'openai_compat',
                          conn: { kind: 'http', baseUrl: 'https://api.openai.com/v1' },
                          modelId: 'gpt-3.5-turbo',
                          status: 'untested',
                          costClass: 'METERED'
                        };
                        setProviders([...providers, newProvider]);
                        onAddProvider?.(newProvider);
                      }}
                      className="px-4 py-2 text-xs font-semibold bg-accent/80 hover:bg-accent text-white rounded transition-colors"
                    >
                      添加OpenAI提供商
                    </button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-text-main mb-1">LLM 提供商配置</h3>
                  <p className="text-[10px] text-text-dim">
                    添加和配置LLM提供商（OpenAI、Ollama、Claude等）
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1 rounded-lg border border-white/10 bg-black/30 p-1">
                    <button
                      type="button"
                      onClick={() => setConfigView('list')}
                      className={`px-3 py-1 text-[10px] font-semibold rounded ${
                        configView === 'list' ? 'bg-cyan-500/70 text-white' : 'text-text-dim hover:text-text-main'
                      }`}
                    >
                      列表
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfigView('visual')}
                      className={`px-3 py-1 text-[10px] font-semibold rounded ${
                        configView === 'visual' ? 'bg-fuchsia-500/70 text-white' : 'text-text-dim hover:text-text-main'
                      }`}
                    >
                      视觉
                    </button>
                  </div>
                  <button
                    onClick={() => {
                      const newProvider = createCodexProvider();
                      setProviders([...providers, newProvider]);
                      onAddProvider?.(newProvider);
                    }}
                    className="px-3 py-1.5 text-[10px] font-semibold bg-emerald-500/70 hover:bg-emerald-500 text-white rounded transition-colors flex items-center gap-1"
                  >
                    <PlayCircle className="size-3" />
                    添加 Codex CLI
                  </button>
                  <button
                    onClick={() => {
                      const newProvider: SimpleProvider = {
                        id: `provider-${Date.now()}`,
                        name: '新提供商',
                        kind: 'openai_compat',
                        conn: { kind: 'http', baseUrl: 'https://api.openai.com/v1' },
                        modelId: 'gpt-3.5-turbo',
                        status: 'untested',
                        costClass: 'METERED'
                      };
                      setProviders([...providers, newProvider]);
                      onAddProvider?.(newProvider);
                    }}
                    className="px-3 py-1.5 text-[10px] font-semibold bg-accent/80 hover:bg-accent text-white rounded transition-colors flex items-center gap-1"
                  >
                    <Plus className="size-3" />
                    添加提供商
                  </button>
                </div>
              </div>

              {configView === 'visual' ? (
                <LLMVisualEditor
                  config={llmConfig}
                  status={llmStatus}
                  onConfigChange={onUpdateConfig}
                  onSave={onSaveConfig}
                />
              ) : (
                <>
                  <div className="space-y-3">
                    {providers.map((provider) => (
                      <SimpleModelCard
                        key={provider.id}
                        provider={provider}
                        renderModelBrowser={
                          provider.kind === 'codex_cli' && isCLIConnection(provider.conn)
                            ? ({ modelId, onSelect }) => (
                                <CodexModelBrowser
                                  providerId={provider.id}
                                  command={provider.conn.command}
                                  tuiArgs={provider.conn.tui_args}
                                  env={provider.conn.env}
                                  modelId={modelId}
                                  onSelect={onSelect}
                                />
                              )
                            : undefined
                        }
                        onUpdate={(updates) => {
                          const updated = { ...provider, ...updates };
                          setProviders(providers.map(p => p.id === provider.id ? updated : p));
                          onUpdateProvider?.(provider.id, updates);
                        }}
                        onDelete={() => {
                          setProviders(providers.filter(p => p.id !== provider.id));
                          onDeleteProvider?.(provider.id);
                        }}
                        onTest={() => openTestPanel(provider.id)}
                      />
                    ))}
                  </div>

                  <div className="flex justify-center">
                    <button
                      onClick={() => setView('hall')}
                      className="px-4 py-2 text-xs font-semibold bg-accent/80 hover:bg-accent text-white rounded transition-colors flex items-center gap-2"
                    >
                      下一步：测试模型
                      <PlayCircle className="size-3" />
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {/* 测试视图 */}
      {view === 'hall' && (
        <InterviewHall
          roles={roles}
          candidates={candidates}
          selectedRole={selectedRole}
          onSelectRole={setSelectedRole}
          onStartInterview={handleStartInterview}
          onRunReadiness={readinessRunning || !canRunReadiness ? undefined : handleRunReadiness}
          disabledReason={disabledReason}
          running={interviewRunning}
        />
      )}

      {/* 面试会话视图 */}
      {view === 'session' && (
        <InterviewSession
          roleLabel={selectedMeta?.label || selectedRole}
          roleId={selectedRole}
          report={interviewReport}
          running={interviewRunning}
          error={interviewError}
          onBack={() => setView('hall')}
        />
      )}

      {panelHost && selectedTestProvider && view === 'config'
        ? createPortal(
            <TestPanel
              provider={selectedTestProvider}
              events={events}
              status={testStatus}
              onClose={closeTestPanel}
              onRunTest={runSelectedTest}
              onCancel={cancelTestRun}
            />,
            panelHost
          )
        : null}
    </div>
  );
}










