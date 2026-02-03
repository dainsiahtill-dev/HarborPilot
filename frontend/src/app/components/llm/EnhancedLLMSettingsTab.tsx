import { Loader2, CheckCircle2, AlertTriangle, Plus, Settings, PlayCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { InterviewHall } from './interview/InterviewHall';
import { InterviewSession } from './interview/InterviewSession';
import { useProviderRegistry } from './ProviderRegistry';
import { type ProviderConfig } from './types';

// Reuse existing interfaces
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
  providers: Record<string, ProviderConfig>;
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

interface EnhancedLLMSettingsTabProps {
  llmConfig: LlmConfig | null;
  llmStatus: LlmStatus | null;
  llmLoading: boolean;
  llmSaving: boolean;
  llmError: string | null;
  deletingProviders?: Record<string, boolean>;
  onSaveConfig: () => void;
  onRunInterview: (role: RoleId) => Promise<Record<string, unknown> | null>;
  onRunReadiness: (role: RoleId) => Promise<Record<string, unknown> | null>;
  onAddProvider?: (providerId: string, provider: ProviderConfig) => void;
  onUpdateProvider?: (providerId: string, updates: Partial<ProviderConfig>) => void;
  onDeleteProvider?: (providerId: string) => void | Promise<void>;
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

export function EnhancedLLMSettingsTab({
  llmConfig,
  llmStatus,
  llmLoading,
  llmSaving,
  llmError,
  deletingProviders,
  onSaveConfig,
  onRunInterview,
  onRunReadiness,
  onAddProvider,
  onUpdateProvider,
  onDeleteProvider
}: EnhancedLLMSettingsTabProps) {
  const [selectedRole, setSelectedRole] = useState<RoleId>('pm');
  const [view, setView] = useState<'config' | 'hall' | 'session'>('config');
  const [interviewReport, setInterviewReport] = useState<InterviewSuiteReport | null>(null);
  const [interviewError, setInterviewError] = useState<string | null>(null);
  const [interviewRunning, setInterviewRunning] = useState(false);
  const [readinessRunning, setReadinessRunning] = useState(false);
  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [selectedProviderType, setSelectedProviderType] = useState<string>('');

  const {
    loading: providersLoading,
    error: providersError,
    providers,
    getProviderInfo,
    getProviderDefaultConfig,
    getProviderComponent,
    requiresApiKey,
    getCostClass,
    validateProviderConfig
  } = useProviderRegistry();

  const roleRequirements = useMemo(() => {
    const policies = llmConfig?.policies?.role_requirements || {};
    return {
      pm: { ...DEFAULT_ROLE_REQUIREMENTS.pm, ...(policies.pm || {}) },
      director: { ...DEFAULT_ROLE_REQUIREMENTS.director, ...(policies.director || {}) },
      qa: { ...DEFAULT_ROLE_REQUIREMENTS.qa, ...(policies.qa || {}) },
      docs: { ...DEFAULT_ROLE_REQUIREMENTS.docs, ...(policies.docs || {}) }
    };
  }, [llmConfig]);

  const roles = useMemo(() => {
    const roleIds: RoleId[] = ['pm', 'director', 'qa', 'docs'];
    return roleIds.map((roleId) => {
      const roleCfg = llmConfig?.roles?.[roleId];
      const providerId = roleCfg?.provider_id || '';
      const providerCfg = providerId ? llmConfig?.providers?.[providerId] : undefined;
      const status = llmStatus?.roles?.[roleId];
      const requirement = roleRequirements[roleId];
      
      return {
        id: roleId,
        label: ROLE_META[roleId].label,
        description: ROLE_META[roleId].description,
        requiresThinking: Boolean(requirement?.requires_thinking),
        minConfidence: requirement?.min_confidence ?? 0.5,
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
        ready: role.readiness?.ready
      }));
  }, [roles]);

  useEffect(() => {
    if (!llmConfig) return;
    if (!roles.find((role) => role.id === selectedRole)) {
      setSelectedRole('pm');
    }
  }, [llmConfig, roles, selectedRole]);

  const globalReadiness = useMemo(() => {
    const state = llmStatus?.state || 'UNKNOWN';
    if (state === 'READY') {
      return { state: 'READY', color: 'text-emerald-400' };
    }
    if (state === 'BLOCKED') {
      return { state: 'BLOCKED', color: 'text-amber-400' };
    }
    return { state: 'UNKNOWN', color: 'text-gray-400' };
  }, [llmStatus]);

  const selectedMeta = roles.find((role) => role.id === selectedRole);
  const canRunReadiness = Boolean(
    selectedMeta?.candidate?.providerId && selectedMeta?.candidate?.model
  );

  const handleAddProvider = async (providerType: string) => {
    if (llmSaving) return;
    const defaultConfig = getProviderDefaultConfig(providerType);
    if (!defaultConfig) return;

    const providerId = `${providerType}-${Date.now()}`;
    const newProvider: ProviderConfig = {
      ...defaultConfig,
      name: defaultConfig.name || `${providerType} Provider`,
      type: providerType
    };

    // Add to config (this would need to be connected to the parent component)
    if (onAddProvider) {
      onAddProvider(providerId, newProvider);
    }
    
    setEditingProvider(providerId);
    setSelectedProviderType(providerType);
  };

  const handleUpdateProvider = (providerId: string, updates: Partial<ProviderConfig>) => {
    // This would need to be connected to the parent component
    if (onUpdateProvider) {
      onUpdateProvider(providerId, updates);
    }
  };

  const handleDeleteProvider = async (providerId: string) => {
    // This would need to be connected to the parent component
    if (deletingProviders?.[providerId]) return;
    if (onDeleteProvider) {
      await onDeleteProvider(providerId);
    }
    if (editingProvider === providerId) {
      setEditingProvider(null);
    }
  };

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

  const renderProviderCard = (providerId: string, provider: ProviderConfig) => {
    const providerInfo = getProviderInfo(provider.type || '');
    const ProviderComponent = getProviderComponent(provider.type || '');
    
    if (!providerInfo) return null;

    const isEditing = editingProvider === providerId;
    const isDeleting = Boolean(deletingProviders?.[providerId]);
    const actionsDisabled = llmSaving || isDeleting;

    return (
      <div key={providerId} className="bg-white/5 rounded-xl p-4 border border-white/10 hover:border-white/20 transition-all">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div>
              <h4 className="text-sm font-semibold text-text-main">{provider.name || providerInfo.name}</h4>
              <div className="flex items-center gap-2 text-[10px] text-text-dim">
                <span className="capitalize">{providerInfo.type}</span>
                <span>•</span>
                <span className="font-mono">{provider.model || "default"}</span>
                <span>•</span>
                <span className={`${getCostClass(provider.type || '').toLowerCase() === 'local' ? 'text-green-400' : getCostClass(provider.type || '').toLowerCase() === 'fixed' ? 'text-blue-400' : 'text-purple-400'}`}>
                  {getCostClass(provider.type || '')}
                </span>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={() => setEditingProvider(isEditing ? null : providerId)}
              disabled={actionsDisabled}
              className="p-1.5 rounded border border-white/10 hover:border-accent/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Settings className="size-3" />
            </button>
            <button
              onClick={() => handleDeleteProvider(providerId)}
              disabled={actionsDisabled}
              className="p-1.5 rounded border border-red-500/30 hover:border-red-500/40 text-red-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isDeleting ? <Loader2 className="size-3 animate-spin" /> : '×'}
            </button>
          </div>
        </div>

        {/* Provider Settings */}
        {isEditing && ProviderComponent ? (
          <div className="space-y-4 pt-4 border-t border-white/10">
            <ProviderComponent
              providerId={providerId}
              provider={provider}
              onUpdate={(updates) => handleUpdateProvider(providerId, updates)}
              onValidate={() => {
                // Return a mock validation result for now
                // In a real implementation, this would be handled by the parent component
                return { valid: true, errors: [], warnings: [] };
              }}
            />
          </div>
        ) : (
          <div className="space-y-3">
            {/* Quick Info */}
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-muted">Type:</span>
              <span className="text-xs text-text-main capitalize">{providerInfo.type}</span>
            </div>
            
            {/* API Key Status */}
            {!requiresApiKey(provider.type || '') && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-text-muted">Authentication:</span>
                <span className="text-xs text-emerald-400">No API Key Required</span>
              </div>
            )}
            
            {/* Usage Class */}
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-muted">Usage Class:</span>
              <span className={`text-xs capitalize ${getCostClass(provider.type || '').toLowerCase() === 'local' ? 'text-green-400' : getCostClass(provider.type || '').toLowerCase() === 'fixed' ? 'text-blue-400' : 'text-purple-400'}`}>
                {getCostClass(provider.type || '')}
              </span>
            </div>

            {/* Features */}
            {providerInfo.supported_features.length > 0 && (
              <div>
                <span className="text-xs text-text-muted">Features:</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {providerInfo.supported_features.slice(0, 3).map((feature) => (
                    <span key={feature} className="text-[9px] bg-accent/20 text-accent px-2 py-1 rounded">
                      {feature}
                    </span>
                  ))}
                  {providerInfo.supported_features.length > 3 && (
                    <span className="text-[9px] text-text-dim">
                      +{providerInfo.supported_features.length - 3} more
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

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
    <div className="space-y-6">
      {/* Navigation */}
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
              disabled={Object.keys(llmConfig?.providers || {}).length === 0}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                view === 'hall' 
                  ? 'bg-accent/20 text-accent border border-accent/30' 
                  : Object.keys(llmConfig?.providers || {}).length === 0
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

        {(llmError || providersError) && (
          <div className="mt-3 text-xs text-status-error bg-status-error/10 border border-status-error/20 rounded p-2">
            {llmError || providersError}
          </div>
        )}
        {llmSaving && (
          <div className="mt-3 flex items-center gap-2 text-[10px] text-text-dim">
            <Loader2 className="size-3 animate-spin" />
            <span>Saving LLM configuration...</span>
          </div>
        )}
      </div>

      {/* Configuration View */}
      {view === 'config' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-text-main mb-1">LLM 提供商配置</h3>
              <p className="text-[10px] text-text-dim">
                添加和配置LLM提供商，支持多种类型和执行模式
              </p>
            </div>
            <div className="flex items-center gap-2">
              {/* Add Provider Dropdown */}
              <select
                value={selectedProviderType}
                onChange={(e) => setSelectedProviderType(e.target.value)}
                className="bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
              >
                <option value="">选择提供商类型</option>
                {providers.map((provider) => (
                  <option key={provider.info.type} value={provider.info.type}>
                    {provider.info.name} ({provider.info.cost_class})
                  </option>
                ))}
              </select>
              <button
                onClick={() => selectedProviderType && handleAddProvider(selectedProviderType)}
                disabled={!selectedProviderType || llmSaving}
                className="px-3 py-1.5 text-[10px] font-semibold bg-accent/80 hover:bg-accent text-white rounded transition-colors flex items-center gap-1 disabled:opacity-60"
              >
                <Plus className="size-3" />
                添加提供商
              </button>
            </div>
          </div>

          {Object.keys(llmConfig?.providers || {}).length === 0 ? (
            <div className="bg-white/5 rounded-xl p-8 border border-white/5 text-center">
              <Settings className="size-8 text-text-dim mx-auto mb-3" />
              <h4 className="text-sm font-medium text-text-main mb-2">尚未配置LLM提供商</h4>
              <p className="text-xs text-text-dim mb-4">
                选择一个提供商类型并添加配置，然后进行模型测试
              </p>
              <div className="text-xs text-text-dim">
                <p>支持的提供商类型：</p>
                <div className="flex flex-wrap gap-2 justify-center mt-2">
                  {providers.slice(0, 6).map((provider) => (
                    <span key={provider.info.type} className="bg-black/30 px-2 py-1 rounded text-[9px]">
                      {provider.info.name}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {Object.entries(llmConfig?.providers || {}).map(([providerId, provider]) =>
                renderProviderCard(providerId, provider)
              )}
            </div>
          )}

          {Object.keys(llmConfig?.providers || {}).length > 0 && (
            <div className="flex justify-center">
              <button
                onClick={() => setView('hall')}
                className="px-4 py-2 text-xs font-semibold bg-accent/80 hover:bg-accent text-white rounded transition-colors flex items-center gap-2"
              >
                下一步：测试模型
                <PlayCircle className="size-3" />
              </button>
            </div>
          )}
        </div>
      )}

      {/* Testing View */}
      {view === 'hall' && (
        <InterviewHall
          roles={roles}
          candidates={candidates}
          selectedRole={selectedRole}
          onSelectRole={setSelectedRole}
          onStartInterview={handleStartInterview}
          onRunReadiness={readinessRunning || !canRunReadiness ? undefined : handleRunReadiness}
          disabledReason={readinessRunning || !canRunReadiness ? "请先选择LLM提供商和模型" : undefined}
          running={interviewRunning}
        />
      )}

      {/* Interview Session View */}
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
    </div>
  );
}
