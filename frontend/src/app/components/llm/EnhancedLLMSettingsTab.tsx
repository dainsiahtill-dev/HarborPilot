import { Loader2, CheckCircle2, AlertTriangle, Plus, Settings, PlayCircle } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  InterviewHall,
  type ConnectivityResult,
  type InterviewProviderSummary
} from './interview/InterviewHall';
import { InterviewSession } from './interview/InterviewSession';
import {
  InteractiveInterviewHall,
  type InteractiveInterviewAnswer,
  type InteractiveInterviewReport
} from './interview/InteractiveInterviewHall';
import { TestPanel } from './test/TestPanel';
import { useTestEvents } from './test/hooks/useTestEvents';
import { LLMVisualEditor } from './visual/LLMVisualEditor';
import { useProviderRegistry } from './ProviderRegistry';
import { PROVIDER_KINDS, isCLIProviderType, type ProviderConfig, type ProviderKind, type SimpleProvider } from './types';
import type { TestEvent, TestResult } from './test/types';
import type { VisualGraphConfig, VisualGraphStatus } from './visual/types/visual';

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
  providers?: Record<
    string,
    {
      ready?: boolean | null;
      grade?: string;
      last_run_id?: string | null;
      timestamp?: string | null;
      suites?: Record<string, unknown> | null;
      model?: string | null;
      role?: string | null;
    }
  >;
}

type RoleId = 'pm' | 'director' | 'qa' | 'docs';

type ConnectionMethodId = 'sdk' | 'api' | 'cli';

interface ConnectionMethodMeta {
  id: ConnectionMethodId;
  label: string;
  description: string;
  pros: string[];
  cons: string[];
  recommended?: boolean;
  accent: string;
  accentText: string;
  accentBorder: string;
}

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
    debug?: boolean;
  }) => Promise<InteractiveInterviewAnswer | null>;
  onSaveInteractiveInterview: (payload: {
    roleId: RoleId;
    providerId: string;
    model: string;
    report: InteractiveInterviewReport;
  }) => Promise<{ saved: boolean; report_path?: string } | null>;
  onAddProvider?: (providerId: string, provider: ProviderConfig) => void;
  onUpdateProvider?: (providerId: string, updates: Partial<ProviderConfig>) => void;
  onDeleteProvider?: (providerId: string) => void | Promise<void>;
  onUpdateConfig?: (config: LlmConfig) => void;
  onTestProvider?: (provider: SimpleProvider, onEvent?: (event: TestEvent) => void) => Promise<TestResult | null>;
  onCancelTestProvider?: () => void;
  onCancelInterview?: () => void;
}

type ConnectivityStatus = 'unknown' | 'running' | 'success' | 'failed';

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

const CONNECTION_METHODS: ConnectionMethodMeta[] = [
  {
    id: 'sdk',
    label: 'SDK 方式',
    description: '官方 SDK 集成，功能完整且稳定',
    pros: ['官方支持', '原生 thinking / streaming', '更好的错误处理', '更完整的功能'],
    cons: ['需要安装 SDK 依赖', '配置项稍多'],
    recommended: true,
    accent: 'bg-emerald-500/15',
    accentText: 'text-emerald-200',
    accentBorder: 'border-emerald-400/40'
  },
  {
    id: 'api',
    label: 'HTTP API 方式',
    description: 'REST API 访问，兼容性最好',
    pros: ['无需 SDK 依赖', '兼容多种服务', '部署简单'],
    cons: ['部分高级功能受限', '流式支持取决于服务端'],
    recommended: false,
    accent: 'bg-cyan-500/15',
    accentText: 'text-cyan-200',
    accentBorder: 'border-cyan-400/40'
  },
  {
    id: 'cli',
    label: '命令行方式',
    description: '使用 CLI 工具，适合本地开发',
    pros: ['本地工具链', '参数灵活', '适合快速试用'],
    cons: ['输出解析复杂', '依赖 CLI 安装'],
    recommended: false,
    accent: 'bg-fuchsia-500/15',
    accentText: 'text-fuchsia-200',
    accentBorder: 'border-fuchsia-400/40'
  }
];

const PROVIDER_FAMILY_ORDER = [
  'Codex',
  'OpenAI',
  'Anthropic',
  'Gemini',
  'MiniMax',
  'Ollama',
  'Custom',
  'Other'
];

const CONNECTIVITY_STORAGE_KEY = 'harborpilot:interview:connectivity';

const parseTimestamp = (value?: string): number => {
  if (!value) return 0;
  const time = Date.parse(value);
  return Number.isNaN(time) ? 0 : time;
};

const extractSuiteOk = (suite: unknown): boolean | undefined => {
  if (!suite || typeof suite !== 'object') return undefined;
  return typeof (suite as { ok?: boolean }).ok === 'boolean' ? Boolean((suite as { ok?: boolean }).ok) : undefined;
};

const extractSuiteLatency = (suites?: Record<string, unknown>): number | undefined => {
  const response = suites?.response as Record<string, unknown> | undefined;
  const details = response?.details as Record<string, unknown> | undefined;
  if (details && typeof details.latency_ms === 'number') {
    return details.latency_ms;
  }
  return undefined;
};

const extractSuiteError = (suites?: Record<string, unknown>): string | undefined => {
  const response = suites?.response as Record<string, unknown> | undefined;
  const responseDetails = response?.details as Record<string, unknown> | undefined;
  if (responseDetails && typeof responseDetails.error === 'string') {
    return responseDetails.error;
  }
  const connectivity = suites?.connectivity as Record<string, unknown> | undefined;
  const connectivityDetails = connectivity?.details as Record<string, unknown> | undefined;
  const healthError = connectivityDetails?.health as Record<string, unknown> | undefined;
  if (healthError && typeof healthError.error === 'string') {
    return healthError.error;
  }
  const modelAvailable = connectivityDetails?.model_available as Record<string, unknown> | undefined;
  if (modelAvailable && typeof modelAvailable.error === 'string') {
    return modelAvailable.error;
  }
  return undefined;
};

const resolveConnectionMethod = (providerType?: string): ConnectionMethodId => {
  const normalized = String(providerType || '').toLowerCase();
  if (normalized.includes('sdk')) return 'sdk';
  if (normalized.includes('cli')) return 'cli';
  return 'api';
};

const resolveProviderFamily = (providerType: string, providerName: string): string => {
  const type = providerType.toLowerCase();
  const name = providerName.toLowerCase();
  if (type.includes('codex') || name.includes('codex')) return 'Codex';
  if (type.includes('openai') || name.includes('openai')) return 'OpenAI';
  if (type.includes('anthropic') || name.includes('anthropic')) return 'Anthropic';
  if (type.includes('gemini') || name.includes('gemini')) return 'Gemini';
  if (type.includes('maxmini') || name.includes('minimax')) return 'MiniMax';
  if (type.includes('ollama') || name.includes('ollama')) return 'Ollama';
  if (type.includes('custom')) return 'Custom';
  return 'Other';
};

const extractThinkingMeta = (suites?: Record<string, unknown>): ConnectivityResult['thinking'] => {
  const thinkingSuite = suites?.thinking as Record<string, unknown> | undefined;
  const details = thinkingSuite?.details as Record<string, unknown> | undefined;
  const thinking = (details?.thinking as Record<string, unknown>) || (thinkingSuite?.thinking as Record<string, unknown>);
  if (!thinking) return undefined;
  return {
    supportsThinking: typeof thinking.supports_thinking === 'boolean' ? thinking.supports_thinking : undefined,
    confidence: typeof thinking.confidence === 'number' ? thinking.confidence : undefined,
    format: typeof thinking.format === 'string' ? thinking.format : undefined
  };
};

const buildConnectivityResultFromSuites = (
  suites: Record<string, unknown> | undefined,
  timestamp?: string,
  model?: string
): ConnectivityResult | null => {
  if (!suites) return null;
  const connectivityOk = extractSuiteOk(suites.connectivity);
  const responseOk = extractSuiteOk(suites.response);
  let ok: boolean | undefined;
  if (connectivityOk !== undefined && responseOk !== undefined) {
    ok = connectivityOk && responseOk;
  } else if (connectivityOk !== undefined) {
    ok = connectivityOk;
  } else if (responseOk !== undefined) {
    ok = responseOk;
  }
  if (ok === undefined) return null;
  return {
    ok,
    timestamp: timestamp || new Date().toISOString(),
    latencyMs: extractSuiteLatency(suites),
    error: extractSuiteError(suites),
    model,
    thinking: extractThinkingMeta(suites)
  };
};

const normalizeConnectivityResult = (value: unknown): ConnectivityResult | null => {
  if (!value || typeof value !== 'object') return null;
  const payload = value as Record<string, unknown>;
  if (typeof payload.ok !== 'boolean' || typeof payload.timestamp !== 'string') {
    return null;
  }
  const thinking = payload.thinking as Record<string, unknown> | undefined;
  return {
    ok: payload.ok,
    timestamp: payload.timestamp,
    latencyMs: typeof payload.latencyMs === 'number' ? payload.latencyMs : undefined,
    error: typeof payload.error === 'string' ? payload.error : undefined,
    model: typeof payload.model === 'string' ? payload.model : undefined,
    sourceRole: typeof payload.sourceRole === 'string' ? payload.sourceRole : undefined,
    thinking: thinking
      ? {
          supportsThinking: typeof thinking.supportsThinking === 'boolean' ? thinking.supportsThinking : undefined,
          confidence: typeof thinking.confidence === 'number' ? thinking.confidence : undefined,
          format: typeof thinking.format === 'string' ? thinking.format : undefined
        }
      : undefined
  };
};

const loadConnectivityCache = (): Map<string, ConnectivityResult> => {
  if (typeof window === 'undefined') return new Map();
  try {
    const raw = window.localStorage.getItem(CONNECTIVITY_STORAGE_KEY);
    if (!raw) return new Map();
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const entries: Array<[string, ConnectivityResult]> = [];
    Object.entries(parsed || {}).forEach(([key, value]) => {
      const normalized = normalizeConnectivityResult(value);
      if (normalized) {
        entries.push([key, normalized]);
      }
    });
    return new Map(entries);
  } catch {
    return new Map();
  }
};

const persistConnectivityCache = (cache: Map<string, ConnectivityResult>) => {
  if (typeof window === 'undefined') return;
  const data: Record<string, ConnectivityResult> = {};
  cache.forEach((value, key) => {
    data[key] = value;
  });
  try {
    window.localStorage.setItem(CONNECTIVITY_STORAGE_KEY, JSON.stringify(data));
  } catch {
    // ignore storage write errors
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
  onRunConnectivityTest,
  onAskInteractiveInterview,
  onSaveInteractiveInterview,
  onAddProvider,
  onUpdateProvider,
  onDeleteProvider,
  onUpdateConfig,
  onTestProvider,
  onCancelTestProvider,
  onCancelInterview
}: EnhancedLLMSettingsTabProps) {
  const [selectedRole, setSelectedRole] = useState<RoleId>('pm');
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'config' | 'deepTest'>('config');
  const [configView, setConfigView] = useState<'list' | 'visual'>('list');
  const [selectedMethod, setSelectedMethod] = useState<ConnectionMethodId>('sdk');
  const [deepView, setDeepView] = useState<'hall' | 'session'>('hall');
  const [interviewMode, setInterviewMode] = useState<'interactive' | 'auto'>('interactive');
  const [interviewReport, setInterviewReport] = useState<InterviewSuiteReport | null>(null);
  const [interviewError, setInterviewError] = useState<string | null>(null);
  const [interviewRunning, setInterviewRunning] = useState(false);
  const [connectivityRunning, setConnectivityRunning] = useState(false);
  const [connectivityRunningKey, setConnectivityRunningKey] = useState<string | null>(null);
  const [connectivityResults, setConnectivityResults] = useState<Map<string, ConnectivityResult>>(
    () => loadConnectivityCache()
  );
  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [selectedProviderType, setSelectedProviderType] = useState<string>('');
  const [selectedTestProviderId, setSelectedTestProviderId] = useState<string | null>(null);
  const [testStatus, setTestStatus] = useState<'idle' | 'running' | 'success' | 'failed'>('idle');
  const [testCancelled, setTestCancelled] = useState(false);
  const [providerTestStatus, setProviderTestStatus] = useState<Record<string, ConnectivityStatus>>({});
  const [interviewPanelOpen, setInterviewPanelOpen] = useState(false);
  const [interviewPanelStatus, setInterviewPanelStatus] = useState<'idle' | 'running' | 'success' | 'failed'>('idle');
  const interviewCancelledRef = useRef(false);
  const methodInitRef = useRef(false);
  const { events, addEvent, resetEvents } = useTestEvents();
  const {
    events: interviewEvents,
    addEvent: addInterviewEvent,
    resetEvents: resetInterviewEvents
  } = useTestEvents();
  const [panelHost, setPanelHost] = useState<HTMLElement | null>(null);

  const {
    loading: providersLoading,
    error: providersError,
    providers,
    getProviderInfo,
    getProviderDefaultConfig,
    getProviderComponent,
    requiresApiKey,
    getCostClass
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

  const availableMethods = useMemo(() => {
    const methodSet = new Set<ConnectionMethodId>();
    providers.forEach((provider) => {
      methodSet.add(resolveConnectionMethod(provider.info.type));
    });
    return Array.from(methodSet);
  }, [providers]);

  const recommendedMethod = useMemo<ConnectionMethodId>(() => {
    if (availableMethods.includes('sdk')) return 'sdk';
    if (availableMethods.includes('api')) return 'api';
    return 'cli';
  }, [availableMethods]);

  const recommendedProvider = useMemo(() => {
    const primaryType =
      recommendedMethod === 'sdk'
        ? 'codex_sdk'
        : recommendedMethod === 'cli'
          ? 'codex_cli'
          : 'openai_compat';
    const preferred = providers.find((provider) => provider.info.type === primaryType);
    if (preferred) return preferred;
    return providers.find((provider) => resolveConnectionMethod(provider.info.type) === recommendedMethod) || null;
  }, [providers, recommendedMethod]);

  const filteredProviderEntries = useMemo(() => {
    return providers.filter((provider) => {
      return resolveConnectionMethod(provider.info.type) === selectedMethod;
    });
  }, [providers, selectedMethod]);

  const providerGroups = useMemo(() => {
    const groups = new Map<string, typeof providers>();
    filteredProviderEntries.forEach((provider) => {
      const family = resolveProviderFamily(provider.info.type, provider.info.name);
      const existing = groups.get(family) || [];
      groups.set(family, [...existing, provider]);
    });
    const ordered: Array<[string, typeof providers]> = [];
    PROVIDER_FAMILY_ORDER.forEach((family) => {
      const entries = groups.get(family);
      if (entries && entries.length > 0) {
        ordered.push([family, entries]);
      }
    });
    groups.forEach((entries, family) => {
      if (!PROVIDER_FAMILY_ORDER.includes(family)) {
        ordered.push([family, entries]);
      }
    });
    return ordered;
  }, [filteredProviderEntries]);

  useEffect(() => {
    if (!methodInitRef.current && availableMethods.length > 0) {
      setSelectedMethod(recommendedMethod);
      methodInitRef.current = true;
      return;
    }
    if (!availableMethods.includes(selectedMethod) && availableMethods.length > 0) {
      setSelectedMethod(recommendedMethod);
    }
  }, [availableMethods, recommendedMethod, selectedMethod]);

  const resolveProviderModel = (
    providerId: string,
    provider: ProviderConfig,
    roles?: Record<string, LlmRoleConfig>
  ): string => {
    const direct = typeof provider.model === 'string' ? provider.model.trim() : '';
    if (direct) return direct;
    const legacy = typeof provider.model_id === 'string' ? provider.model_id.trim() : '';
    if (legacy) return legacy;
    const fallback = typeof provider.default_model === 'string' ? provider.default_model.trim() : '';
    if (fallback) return fallback;
    if (!roles) return '';
    for (const roleCfg of Object.values(roles)) {
      if (!roleCfg || typeof roleCfg !== 'object') continue;
      if (roleCfg.provider_id === providerId && roleCfg.model) {
        return roleCfg.model;
      }
    }
    return '';
  };

  const buildSimpleProvider = (
    providerId: string,
    provider: ProviderConfig,
    roles?: Record<string, LlmRoleConfig>
  ): SimpleProvider => {
    const kind = (provider.type || PROVIDER_KINDS.OPENAI_COMPAT) as ProviderKind;
    const isCli = isCLIProviderType(provider.type) || Boolean(provider.command);
    const conn = isCli
      ? {
          kind: kind === PROVIDER_KINDS.GEMINI_CLI ? 'gemini_cli' : 'codex_cli',
          command: provider.command || (kind === PROVIDER_KINDS.GEMINI_CLI ? 'gemini' : 'codex'),
          args: provider.args || [],
          env: provider.env || {}
        }
      : {
          kind: 'http',
          baseUrl: provider.base_url || '',
          apiKey: provider.api_key
        };
    const modelId = resolveProviderModel(providerId, provider, roles);
    return {
      id: providerId,
      name: provider.name || providerId,
      kind,
      conn,
      cliMode: provider.cli_mode,
      modelId,
      status: 'untested'
    };
  };

  const getConnectivityKey = (roleId: RoleId, providerId: string) => `${roleId}::${providerId}`;

  const resolveModelForSelection = (roleId: RoleId, providerId: string): string => {
    const providerCfg = llmConfig?.providers?.[providerId];
    const providerModel = providerCfg ? resolveProviderModel(providerId, providerCfg, llmConfig?.roles) : '';
    const roleCfg = llmConfig?.roles?.[roleId];
    const roleModel = roleCfg?.provider_id === providerId ? roleCfg.model || '' : '';
    return providerModel || roleModel || '';
  };

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

  useEffect(() => {
    if (!llmConfig) return;
    if (!roles.find((role) => role.id === selectedRole)) {
      setSelectedRole('pm');
    }
  }, [llmConfig, roles, selectedRole]);

  useEffect(() => {
    if (!llmConfig) {
      setSelectedProviderId(null);
      return;
    }
    const providerIds = Object.keys(llmConfig.providers || {});
    if (providerIds.length === 0) {
      setSelectedProviderId(null);
      return;
    }
    if (selectedProviderId && providerIds.includes(selectedProviderId)) {
      return;
    }
    const roleProvider = llmConfig.roles?.[selectedRole]?.provider_id;
    if (roleProvider && providerIds.includes(roleProvider)) {
      setSelectedProviderId(roleProvider);
      return;
    }
    setSelectedProviderId(providerIds[0]);
  }, [llmConfig, selectedRole, selectedProviderId]);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    setPanelHost(document.getElementById('llm-test-panel-slot'));
  }, []);

  useEffect(() => {
    setInterviewError(null);
  }, [selectedRole, selectedProviderId]);

  useEffect(() => {
    if (!selectedRole || !selectedProviderId) return;
    const key = getConnectivityKey(selectedRole, selectedProviderId);
    if (connectivityResults.has(key)) return;
    let latest: { value: ConnectivityResult; role?: string } | null = null;
    connectivityResults.forEach((value, mapKey) => {
      if (!mapKey.endsWith(`::${selectedProviderId}`)) return;
      const time = parseTimestamp(value.timestamp);
      if (!latest || time >= parseTimestamp(latest.value.timestamp)) {
        latest = { value, role: mapKey.split('::')[0] };
      }
    });
    if (!latest) return;
    const desiredModel = resolveModelForSelection(selectedRole, selectedProviderId);
    const latestModel = latest.value.model || '';
    if (desiredModel && latestModel && desiredModel !== latestModel) {
      return;
    }
    const adopted: ConnectivityResult = {
      ...latest.value,
      model: desiredModel || latest.value.model,
      sourceRole: latest.role
    };
    setConnectivityResults((prev) => {
      if (prev.has(key)) return prev;
      const next = new Map(prev);
      next.set(key, adopted);
      return next;
    });
  }, [connectivityResults, llmConfig, selectedProviderId, selectedRole]);

  useEffect(() => {
    persistConnectivityCache(connectivityResults);
  }, [connectivityResults]);

  useEffect(() => {
    if (!llmStatus?.providers) return;
    setConnectivityResults((prev) => {
      const next = new Map(prev);
      Object.entries(llmStatus.providers || {}).forEach(([providerId, providerStatus]) => {
        if (!providerStatus || typeof providerStatus !== 'object') return;
        const suites = providerStatus.suites as Record<string, unknown> | undefined;
        if (!suites) return;
        const result = buildConnectivityResultFromSuites(
          suites,
          typeof providerStatus.timestamp === 'string' ? providerStatus.timestamp : undefined,
          typeof providerStatus.model === 'string' ? providerStatus.model : undefined
        );
        if (!result) return;
        const role = typeof providerStatus.role === 'string' ? providerStatus.role : '';
        if (!role) return;
        const key = `${role}::${providerId}`;
        const existing = next.get(key);
        if (!existing || parseTimestamp(result.timestamp) >= parseTimestamp(existing.timestamp)) {
          next.set(key, result);
        }
      });
      return next;
    });
  }, [llmStatus]);

  useEffect(() => {
    if (!selectedTestProviderId) return;
    if (!llmConfig?.providers?.[selectedTestProviderId]) {
      closeTestPanel();
    }
  }, [llmConfig, selectedTestProviderId]);

  useEffect(() => {
    if (activeTab !== 'config' && selectedTestProviderId) {
      closeTestPanel();
    }
  }, [activeTab, selectedTestProviderId]);

  useEffect(() => {
    if (activeTab !== 'deepTest' && interviewPanelOpen) {
      setInterviewPanelOpen(false);
      setInterviewPanelStatus('idle');
      resetInterviewEvents();
    }
  }, [activeTab, interviewPanelOpen, resetInterviewEvents]);

  const selectedTestProvider = useMemo(() => {
    if (!selectedTestProviderId || !llmConfig) return null;
    const cfg = llmConfig.providers?.[selectedTestProviderId];
    if (!cfg) return null;
    return buildSimpleProvider(selectedTestProviderId, cfg, llmConfig.roles);
  }, [llmConfig, selectedTestProviderId]);

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
    if (selectedTestProviderId) {
      setProviderTestStatus((prev) => ({ ...prev, [selectedTestProviderId]: 'unknown' }));
    }
    addEvent({
      type: 'error',
      timestamp: new Date().toISOString(),
      content: 'Test cancelled by user'
    });
    setTestStatus('failed');
  };

  const cancelInterviewRun = () => {
    if (onCancelInterview) {
      onCancelInterview();
    }
    interviewCancelledRef.current = true;
    setInterviewPanelStatus('failed');
    addInterviewEvent({
      type: 'error',
      timestamp: new Date().toISOString(),
      content: '面试已取消'
    });
  };

  const openInterviewPanel = () => {
    setInterviewPanelOpen(true);
    setInterviewPanelStatus('idle');
    resetInterviewEvents();
  };

  const closeInterviewPanel = () => {
    setInterviewPanelOpen(false);
    setInterviewPanelStatus('idle');
    resetInterviewEvents();
  };

  const shouldSkipErrorEvent = (err: unknown): boolean => {
    if (!err || typeof err !== 'object') return false;
    return 'skipUiEvent' in err && Boolean((err as { skipUiEvent?: boolean }).skipUiEvent);
  };

  const runSelectedTest = async () => {
    if (!selectedTestProvider || !onTestProvider) return;
    setProviderTestStatus((prev) => ({ ...prev, [selectedTestProvider.id]: 'running' }));
    setTestStatus('running');
    setTestCancelled(false);
    resetEvents();
    addEvent({
      type: 'command',
      timestamp: new Date().toISOString(),
      content: `Preparing test for ${selectedTestProvider.name}`
    });
    try {
      const result = await onTestProvider(selectedTestProvider, (event) => {
        addEvent(event);
      });
      if (!result) {
        setProviderTestStatus((prev) => ({
          ...prev,
          [selectedTestProvider.id]: testCancelled ? 'unknown' : 'failed'
        }));
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
        return;
      }
      const connectivitySuite = result.suites?.find((suite) => suite.name === 'connectivity');
      const ready = result.ready ?? result.grade === 'PASS';
      const connectivityStatus: ConnectivityStatus = connectivitySuite
        ? connectivitySuite.ok
          ? 'success'
          : 'failed'
        : ready
          ? 'success'
          : 'failed';
      setProviderTestStatus((prev) => ({ ...prev, [selectedTestProvider.id]: connectivityStatus }));
      setTestStatus(ready ? 'success' : 'failed');
      addEvent({
        type: ready ? 'result' : 'error',
        timestamp: new Date().toISOString(),
        content: ready ? '测试完成' : '测试未通过'
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : '测试失败';
      if (selectedTestProvider) {
        setProviderTestStatus((prev) => ({ ...prev, [selectedTestProvider.id]: 'failed' }));
      }
      setTestStatus('failed');
      if (!shouldSkipErrorEvent(err)) {
        addEvent({
          type: 'error',
          timestamp: new Date().toISOString(),
          content: message
        });
      }
    }
  };

  const providerConnectivityStatus = useMemo(() => {
    const status: Record<string, ConnectivityStatus> = {};
    const providersStatus = llmStatus?.providers;
    if (!providersStatus) return status;
    Object.entries(providersStatus).forEach(([providerId, providerStatus]) => {
      if (!providerStatus || typeof providerStatus !== 'object') {
        status[providerId] = 'unknown';
        return;
      }
      const suites = providerStatus.suites as Record<string, unknown> | undefined;
      const connectivity = suites?.connectivity as Record<string, unknown> | undefined;
      if (connectivity && typeof connectivity.ok === 'boolean') {
        status[providerId] = connectivity.ok ? 'success' : 'failed';
        return;
      }
      if (typeof providerStatus.ready === 'boolean') {
        status[providerId] = providerStatus.ready ? 'success' : 'failed';
        return;
      }
      status[providerId] = 'unknown';
    });
    return status;
  }, [llmStatus]);

  const interviewProviders = useMemo<InterviewProviderSummary[]>(() => {
    if (!llmConfig) return [];
    const providersConfig = llmConfig.providers || {};
    const getLatestConnectivity = (providerId: string): ConnectivityResult | undefined => {
      if (selectedRole) {
        const direct = connectivityResults.get(`${selectedRole}::${providerId}`);
        if (direct) return direct;
      }
      let best: ConnectivityResult | undefined;
      connectivityResults.forEach((value, key) => {
        if (!key.endsWith(`::${providerId}`)) return;
        if (!best || parseTimestamp(value.timestamp) > parseTimestamp(best.timestamp)) {
          best = value;
        }
      });
      return best;
    };

    return Object.entries(providersConfig).map(([providerId, providerCfg]) => {
      const providerInfo = getProviderInfo(providerCfg.type || '');
      const model = resolveProviderModel(providerId, providerCfg, llmConfig.roles);
      const suites = llmStatus?.providers?.[providerId]?.suites as Record<string, unknown> | undefined;
      const thinkingMeta = extractThinkingMeta(suites);
      const connectivity = getLatestConnectivity(providerId);
      const isTesting = connectivityRunningKey?.endsWith(`::${providerId}`);
      const status: InterviewProviderSummary['status'] = isTesting
        ? 'testing'
        : connectivity?.ok === true
          ? 'ready'
          : connectivity?.ok === false
            ? 'failed'
            : 'untested';
      return {
        id: providerId,
        name: providerCfg.name || providerInfo?.name || providerId,
        model,
        providerType: providerCfg.type || providerInfo?.type || 'unknown',
        status,
        thinkingSupported: thinkingMeta?.supportsThinking,
        thinkingConfidence: thinkingMeta?.confidence ?? null,
        lastConnectivityTest: connectivity
          ? {
              timestamp: connectivity.timestamp,
              success: connectivity.ok,
              latencyMs: connectivity.latencyMs,
              error: connectivity.error
            }
          : undefined
      };
    });
  }, [connectivityResults, connectivityRunningKey, getProviderInfo, llmConfig, llmStatus, selectedRole]);

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

  const visualConfig = useMemo(
    () => (llmConfig ? (llmConfig as unknown as VisualGraphConfig) : null),
    [llmConfig]
  );

  const visualStatus = useMemo(() => {
    if (!llmStatus) return null;
    const rolesStatus: Record<string, { ready?: boolean; grade?: string }> = {};
    Object.entries(llmStatus.roles || {}).forEach(([roleId, role]) => {
      rolesStatus[roleId] = { ready: role.ready, grade: role.grade };
    });
    return { roles: rolesStatus } as VisualGraphStatus;
  }, [llmStatus]);

  const handleVisualConfigChange = (nextConfig: VisualGraphConfig) => {
    if (!onUpdateConfig) return;
    onUpdateConfig(nextConfig as LlmConfig);
  };

  const selectedMeta = roles.find((role) => role.id === selectedRole);

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

  const handleStartInterview = async (roleId: RoleId, providerId: string) => {
    const activeMeta = roles.find((role) => role.id === roleId);
    if (!activeMeta) return;
    const model = resolveModelForSelection(roleId, providerId);
    if (!model) {
      setInterviewError('缺少模型配置，无法开始面试');
      return;
    }
    const connectivityKey = getConnectivityKey(roleId, providerId);
    const connectivity = connectivityResults.get(connectivityKey);
    if (!connectivity?.ok) {
      setInterviewError('请先通过连通性测试');
      return;
    }
    setSelectedRole(roleId);
    setSelectedProviderId(providerId);
    openInterviewPanel();
    setInterviewError(null);
    setInterviewReport(null);
    setInterviewRunning(true);
    interviewCancelledRef.current = false;
    setInterviewPanelStatus('running');
    setActiveTab('deepTest');
    setDeepView('session');
    try {
      addInterviewEvent({
        type: 'command',
        timestamp: new Date().toISOString(),
        content: `Starting interview for ${activeMeta.label}`
      });
      const report = await onRunInterview(roleId, providerId, model, (event) => addInterviewEvent(event));
      if (!report) {
        const cancelledMessage = interviewCancelledRef.current ? '面试已取消' : '面试未返回结果';
        setInterviewPanelStatus('failed');
        addInterviewEvent({
          type: 'error',
          timestamp: new Date().toISOString(),
          content: cancelledMessage
        });
        return;
      }
      const suiteReport = (report?.suites as Record<string, unknown> | undefined)?.interview;
      if (suiteReport && typeof suiteReport === 'object') {
        setInterviewReport(suiteReport as InterviewSuiteReport);
      } else if (report && typeof report === 'object') {
        setInterviewReport(report as InterviewSuiteReport);
      } else {
        setInterviewReport(null);
      }
      const suiteOk =
        suiteReport && typeof (suiteReport as { ok?: boolean }).ok === 'boolean'
          ? Boolean((suiteReport as { ok?: boolean }).ok)
          : report?.final && typeof (report.final as { ready?: boolean }).ready === 'boolean'
            ? Boolean((report.final as { ready?: boolean }).ready)
            : false;
      setInterviewPanelStatus(suiteOk ? 'success' : 'failed');
      addInterviewEvent({
        type: suiteOk ? 'result' : 'error',
        timestamp: new Date().toISOString(),
        content: suiteOk ? '面试完成' : '面试未通过'
      });
    } catch (error) {
      setInterviewError(error instanceof Error ? error.message : 'Interview failed');
      setInterviewPanelStatus('failed');
      addInterviewEvent({
        type: 'error',
        timestamp: new Date().toISOString(),
        content: error instanceof Error ? error.message : 'Interview failed'
      });
    } finally {
      setInterviewRunning(false);
    }
  };

  const handleInteractiveAsk = async (payload: {
    roleId: RoleId;
    providerId: string;
    question: string;
    expectedCriteria?: string[];
    expectsThinking?: boolean;
    sessionId?: string | null;
    context?: Array<{ question: string; answer: string }>;
    debug?: boolean;
  }): Promise<InteractiveInterviewAnswer | null> => {
    const model = resolveModelForSelection(payload.roleId, payload.providerId);
    if (!model) {
      throw new Error('缺少模型配置，无法发送问题');
    }
    return onAskInteractiveInterview({
      roleId: payload.roleId,
      providerId: payload.providerId,
      model,
      question: payload.question,
      expectedCriteria: payload.expectedCriteria,
      expectsThinking: payload.expectsThinking,
      sessionId: payload.sessionId,
      context: payload.context,
      debug: payload.debug
    });
  };

  const handleInteractiveSave = async (payload: {
    roleId: RoleId;
    providerId: string;
    report: InteractiveInterviewReport;
  }): Promise<{ saved: boolean; report_path?: string } | null> => {
    const model = resolveModelForSelection(payload.roleId, payload.providerId);
    if (!model) {
      throw new Error('缺少模型配置，无法保存面试报告');
    }
    return onSaveInteractiveInterview({
      roleId: payload.roleId,
      providerId: payload.providerId,
      model,
      report: payload.report
    });
  };

  const handleRunConnectivity = async (roleId: RoleId, providerId: string) => {
    if (!onRunConnectivityTest) return;
    const model = resolveModelForSelection(roleId, providerId);
    const key = getConnectivityKey(roleId, providerId);
    if (!model) {
      const result: ConnectivityResult = {
        ok: false,
        timestamp: new Date().toISOString(),
        error: '缺少模型配置，无法执行连通性测试'
      };
      setConnectivityResults((prev) => {
        const next = new Map(prev);
        next.set(key, result);
        return next;
      });
      return;
    }
    setConnectivityRunning(true);
    setConnectivityRunningKey(key);
    try {
      const report = await onRunConnectivityTest(roleId, providerId, model);
      const suites = report?.suites as Record<string, unknown> | undefined;
      const reportTimestamp = typeof report?.timestamp === 'string' ? report.timestamp : new Date().toISOString();
      const result =
        buildConnectivityResultFromSuites(suites, reportTimestamp, model) ||
        ({
          ok: false,
          timestamp: reportTimestamp,
          error: '连通性测试未返回结果',
          model
        } as ConnectivityResult);
      setConnectivityResults((prev) => {
        const next = new Map(prev);
        next.set(key, result);
        return next;
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : '连通性测试失败';
      const result: ConnectivityResult = {
        ok: false,
        timestamp: new Date().toISOString(),
        error: message,
        model
      };
      setConnectivityResults((prev) => {
        const next = new Map(prev);
        next.set(key, result);
        return next;
      });
    } finally {
      setConnectivityRunning(false);
      setConnectivityRunningKey(null);
    }
  };

  const renderProviderCard = (providerId: string, provider: ProviderConfig) => {
    const providerInfo = getProviderInfo(provider.type || '');
    const ProviderComponent = getProviderComponent(provider.type || '');
    
    if (!providerInfo) return null;

    const isEditing = editingProvider === providerId;
    const isDeleting = Boolean(deletingProviders?.[providerId]);
    const actionsDisabled = llmSaving || isDeleting;
    const testDisabled = actionsDisabled || !onTestProvider;

    const localStatus = providerTestStatus[providerId];
    const persistedStatus = providerConnectivityStatus[providerId];
    const connectivityState =
      localStatus === 'running'
        ? 'running'
        : persistedStatus || localStatus || 'unknown';
    const statusStyleKey = connectivityState === 'running' ? 'unknown' : connectivityState;
    const statusStyles = {
      unknown: {
        border: 'border-amber-500/30',
        bg: 'bg-amber-500/5',
        glow: 'shadow-[0_0_24px_rgba(251,191,36,0.15)]',
        dot: 'bg-amber-400',
        text: 'text-amber-300'
      },
      success: {
        border: 'border-emerald-500/40',
        bg: 'bg-emerald-500/5',
        glow: 'shadow-[0_0_24px_rgba(16,185,129,0.18)]',
        dot: 'bg-emerald-400',
        text: 'text-emerald-300'
      },
      failed: {
        border: 'border-rose-500/40',
        bg: 'bg-rose-500/5',
        glow: 'shadow-[0_0_24px_rgba(244,63,94,0.18)]',
        dot: 'bg-rose-400',
        text: 'text-rose-300'
      }
    }[statusStyleKey];
    const connectivityLabel =
      connectivityState === 'running'
        ? '测试中'
        : connectivityState === 'success'
          ? '连通正常'
          : connectivityState === 'failed'
            ? '连通失败'
            : '连通未知';

    return (
      <div
        key={providerId}
        className={`rounded-xl p-4 border transition-all ${statusStyles.border} ${statusStyles.bg} ${statusStyles.glow}`}
      >
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
                <span>•</span>
                <span className={`flex items-center gap-1 ${statusStyles.text}`}>
                  <span className={`size-2 rounded-full ${statusStyles.dot} animate-pulse`} />
                  {connectivityLabel}
                </span>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={() => openTestPanel(providerId)}
              disabled={testDisabled}
              className="p-1.5 rounded border border-cyan-500/30 hover:border-cyan-500/60 text-cyan-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <PlayCircle className="size-3" />
            </button>
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

  const interviewProvider = useMemo(() => {
    if (!selectedProviderId || !llmConfig?.providers?.[selectedProviderId]) return null;
    const providerCfg = llmConfig.providers[selectedProviderId];
    const baseProvider = buildSimpleProvider(selectedProviderId, providerCfg, llmConfig.roles);
    const resolvedModel =
      selectedRole && selectedProviderId
        ? resolveModelForSelection(selectedRole, selectedProviderId)
        : baseProvider.modelId;
    const modelId = resolvedModel || baseProvider.modelId;
    return {
      ...baseProvider,
      name: `Interview · ${selectedMeta?.label || selectedProviderId}`,
      modelId
    };
  }, [buildSimpleProvider, llmConfig, selectedMeta, selectedProviderId, selectedRole]);

  const selectedInterviewModel = useMemo(() => {
    if (!selectedRole || !selectedProviderId) return '';
    return resolveModelForSelection(selectedRole, selectedProviderId);
  }, [llmConfig, selectedProviderId, selectedRole]);

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
      <div className="rounded-2xl border border-cyan-500/20 bg-[radial-gradient(circle_at_top,_rgba(14,116,144,0.22),_transparent_60%)] p-4 shadow-[0_0_30px_rgba(34,211,238,0.2)]">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('config')}
              className={`px-4 py-2 text-[11px] font-semibold uppercase tracking-wider rounded-lg border transition-all ${
                activeTab === 'config'
                  ? 'bg-cyan-500/20 text-cyan-200 border-cyan-400/40 shadow-[0_0_16px_rgba(34,211,238,0.25)]'
                  : 'text-text-dim border-white/10 hover:border-cyan-400/40 hover:text-cyan-100'
              }`}
            >
              CONFIG
            </button>
            <button
              onClick={() => {
                setActiveTab('deepTest');
                setDeepView('hall');
              }}
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

      {/* CONFIG Tab */}
      {activeTab === 'config' && (
        <div className="space-y-4">
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
            <div className="space-y-4">
              <div className="rounded-2xl border border-white/10 bg-black/40 p-4 shadow-[0_0_22px_rgba(34,211,238,0.12)]">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-xs font-semibold text-text-main">连接方式选择</div>
                    <div className="text-[10px] text-text-dim">先选连接方式，再选具体提供商。</div>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-text-dim">
                    <span>推荐优先：</span>
                    <span className="px-2 py-1 rounded border border-emerald-400/40 bg-emerald-500/10 text-emerald-200">
                      {CONNECTION_METHODS.find((item) => item.id === recommendedMethod)?.label}
                    </span>
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
                  {CONNECTION_METHODS.map((method) => {
                    const selected = selectedMethod === method.id;
                    return (
                      <button
                        key={method.id}
                        type="button"
                        onClick={() => setSelectedMethod(method.id)}
                        className={`text-left rounded-xl border p-3 transition-all ${
                          selected
                            ? `${method.accentBorder} ${method.accent} shadow-[0_0_18px_rgba(34,211,238,0.15)]`
                            : 'border-white/10 bg-black/20 hover:border-white/30'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className={`text-xs font-semibold ${selected ? method.accentText : 'text-text-main'}`}>
                            {method.label}
                          </span>
                          {method.recommended ? (
                            <span className="text-[9px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-200 border border-emerald-500/40">
                              推荐
                            </span>
                          ) : null}
                        </div>
                        <div className="mt-1 text-[10px] text-text-dim">{method.description}</div>
                        <div className="mt-2 grid grid-cols-2 gap-2 text-[10px] text-text-dim">
                          <div className="space-y-1">
                            <div className="text-[9px] uppercase tracking-wider text-text-dim">优势</div>
                            <div className="flex flex-wrap gap-1">
                              {method.pros.slice(0, 2).map((item) => (
                                <span key={item} className="px-2 py-0.5 rounded bg-white/5 text-text-dim">
                                  {item}
                                </span>
                              ))}
                            </div>
                          </div>
                          <div className="space-y-1">
                            <div className="text-[9px] uppercase tracking-wider text-text-dim">限制</div>
                            <div className="flex flex-wrap gap-1">
                              {method.cons.slice(0, 2).map((item) => (
                                <span key={item} className="px-2 py-0.5 rounded bg-white/5 text-text-dim">
                                  {item}
                                </span>
                              ))}
                            </div>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>

                {recommendedProvider ? (
                  <div className="mt-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3 text-[10px] text-emerald-100 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      推荐提供商：<span className="font-semibold">{recommendedProvider.info.name}</span>
                      <span className="text-emerald-200/70"> · {recommendedProvider.info.description}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleAddProvider(recommendedProvider.info.type)}
                      className="px-3 py-1.5 rounded bg-emerald-500/80 text-white text-[10px] font-semibold hover:bg-emerald-500 transition-colors"
                    >
                      一键添加
                    </button>
                  </div>
                ) : null}
              </div>

              <div className="rounded-2xl border border-white/10 bg-black/30 p-4">
                <div className="flex items-center justify-between gap-3 mb-3">
                  <div>
                    <div className="text-xs font-semibold text-text-main">支持的提供商</div>
                    <div className="text-[10px] text-text-dim">
                      当前显示：{CONNECTION_METHODS.find((item) => item.id === selectedMethod)?.label}
                    </div>
                  </div>
                  <div className="text-[10px] text-text-dim">
                    选择后将自动创建配置并进入编辑模式。
                  </div>
                </div>

                {providerGroups.length === 0 ? (
                  <div className="text-xs text-text-dim">暂无可用提供商</div>
                ) : (
                  <div className="space-y-4">
                    {providerGroups.map(([family, entries]) => (
                      <div key={family} className="space-y-2">
                        <div className="text-[11px] uppercase tracking-wider text-text-dim">{family}</div>
                        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                          {entries.map((provider) => {
                            const selected = selectedProviderType === provider.info.type;
                            return (
                              <button
                                key={provider.info.type}
                                type="button"
                                onClick={() => handleAddProvider(provider.info.type)}
                                disabled={llmSaving}
                                className={`text-left rounded-xl border p-3 transition-all ${
                                  selected
                                    ? 'border-cyan-400/50 bg-cyan-500/10'
                                    : 'border-white/10 bg-black/20 hover:border-white/30'
                                } disabled:opacity-60`}
                              >
                                <div className="flex items-center justify-between gap-2">
                                  <div>
                                    <div className="text-xs font-semibold text-text-main">{provider.info.name}</div>
                                    <div className="text-[10px] text-text-dim">{provider.info.type}</div>
                                  </div>
                                  <span className="text-[9px] px-2 py-0.5 rounded border border-white/10 bg-black/40">
                                    {provider.info.cost_class}
                                  </span>
                                </div>
                                <div className="mt-2 text-[10px] text-text-dim line-clamp-2">
                                  {provider.info.description}
                                </div>
                                {provider.info.supported_features?.length ? (
                                  <div className="mt-2 flex flex-wrap gap-1">
                                    {provider.info.supported_features.slice(0, 3).map((feature) => (
                                      <span key={feature} className="text-[9px] px-2 py-0.5 rounded bg-white/5 text-text-dim">
                                        {feature}
                                      </span>
                                    ))}
                                  </div>
                                ) : null}
                                <div className="mt-2 flex items-center justify-between text-[10px] text-text-dim">
                                  <span>点击添加并配置</span>
                                  <Plus className="size-3" />
                                </div>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
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
                <div className="flex justify-center">
                  <button
                    onClick={() => {
                      setActiveTab('deepTest');
                      setDeepView('hall');
                    }}
                    className="px-4 py-2 text-xs font-semibold bg-emerald-500/80 hover:bg-emerald-500 text-white rounded transition-colors flex items-center gap-2"
                  >
                    进入深度测试
                    <PlayCircle className="size-3" />
                  </button>
                </div>
              </div>
            )}
          </div>
          )}
        </div>
      )}

      {/* DEEP TEST Tab */}
      {activeTab === 'deepTest' && (
        <div className="space-y-4 w-full max-w-5xl mx-auto min-h-[60vh]">
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

          <div className="w-full">
            {interviewMode === 'interactive' ? (
              <InteractiveInterviewHall
                roles={roles}
                providers={interviewProviders}
                selectedRole={selectedRole}
                selectedProvider={selectedProviderId}
                selectedModel={selectedInterviewModel}
                onSelectRole={setSelectedRole}
                onSelectProvider={setSelectedProviderId}
                onAskQuestion={handleInteractiveAsk}
                onSaveReport={handleInteractiveSave}
              />
            ) : deepView === 'hall' ? (
              <InterviewHall
                roles={roles}
                selectedRole={selectedRole}
                providers={interviewProviders}
                selectedProvider={selectedProviderId}
                onSelectRole={setSelectedRole}
                onSelectProvider={setSelectedProviderId}
                onRunConnectivityTest={handleRunConnectivity}
                onRunInterview={handleStartInterview}
                connectivityResults={connectivityResults}
                interviewRunning={interviewRunning}
                connectivityRunning={connectivityRunning}
              />
            ) : (
              <InterviewSession
                roleLabel={selectedMeta?.label || selectedRole}
                roleId={selectedRole}
                report={interviewReport}
                running={interviewRunning}
                error={interviewError}
                onBack={() => setDeepView('hall')}
              />
            )}
          </div>
        </div>
      )}

      {panelHost && selectedTestProvider && activeTab === 'config'
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

      {panelHost && interviewPanelOpen && interviewProvider && activeTab === 'deepTest'
        ? createPortal(
            <TestPanel
              provider={interviewProvider}
              events={interviewEvents}
              status={interviewPanelStatus}
              onClose={closeInterviewPanel}
              onRunTest={() => {
                if (selectedRole && selectedProviderId) {
                  handleStartInterview(selectedRole, selectedProviderId);
                }
              }}
              onCancel={cancelInterviewRun}
            />,
            panelHost
          )
        : null}
    </div>
  );
}
