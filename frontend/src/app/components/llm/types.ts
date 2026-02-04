// Unified LLM Provider Types
// This file centralizes all type definitions to avoid duplication and inconsistency

// Provider Categories
export const PROVIDER_CATEGORIES = {
  AGENT: 'AGENT' as const,
  LLM: 'LLM' as const
} as const;

export type ProviderCategory = typeof PROVIDER_CATEGORIES[keyof typeof PROVIDER_CATEGORIES];

// Provider Kinds (specific provider types)
export const PROVIDER_KINDS = {
  CODEX_CLI: 'codex_cli' as const,
  CODEX_SDK: 'codex_sdk' as const,
  GEMINI_CLI: 'gemini_cli' as const,
  OLLAMA: 'ollama' as const,
  OPENAI_COMPAT: 'openai_compat' as const,
  ANTHROPIC_COMPAT: 'anthropic_compat' as const,
  CUSTOM_HTTPS: 'custom_https' as const,
  MAXMINI: 'maxmini' as const,
  GEMINI_API: 'gemini_api' as const
} as const;

export type ProviderKind = typeof PROVIDER_KINDS[keyof typeof PROVIDER_KINDS];

// Connection Types
export type CLIConnectionKind = 'codex_cli' | 'gemini_cli';
export type HTTPConnectionKind = 'http';

// CLI Modes
export const CLI_MODES = {
  TUI: 'tui' as const,
  HEADLESS: 'headless' as const
} as const;

export type CLIMode = typeof CLI_MODES[keyof typeof CLI_MODES];

export type CLIConnection = {
  kind: CLIConnectionKind;
  command: string;
  args?: string[];
  env?: Record<string, string>;
};

export type HTTPConnection = {
  kind: HTTPConnectionKind;
  baseUrl: string;
  apiKey?: string;
};

export type ProviderConnection = CLIConnection | HTTPConnection;

// Provider Status
export const PROVIDER_STATUS = {
  UNTESTED: 'untested' as const,
  TESTING: 'testing' as const,
  READY: 'ready' as const,
  FAILED: 'failed' as const
} as const;

export type ProviderStatus = typeof PROVIDER_STATUS[keyof typeof PROVIDER_STATUS];

// Cost Classes
export const COST_CLASSES = {
  LOCAL: 'LOCAL' as const,
  FIXED: 'FIXED' as const,
  METERED: 'METERED' as const
} as const;

export type CostClass = typeof COST_CLASSES[keyof typeof COST_CLASSES];

// Model Listing Methods
export const MODEL_LISTING_METHODS = {
  API: 'API' as const,
  TUI: 'TUI' as const,
  NONE: 'NONE' as const
} as const;

export type ModelListingMethod = typeof MODEL_LISTING_METHODS[keyof typeof MODEL_LISTING_METHODS];

// Provider Info (from backend)
export interface ProviderInfo {
  name: string;
  type: string;
  description: string;
  version: string;
  author: string;
  documentation_url: string;
  supported_features: string[];
  cost_class: CostClass;
  provider_category: ProviderCategory;
  autonomous_file_access: boolean;
  requires_file_interfaces: boolean;
  model_listing_method: ModelListingMethod;
}

// Provider Config (frontend)
export interface ProviderConfig {
  type?: string;
  name?: string;
  command?: string;
  args?: string[];
  codex_exec?: Record<string, unknown>;
  env?: Record<string, string>;
  base_url?: string;
  api_key?: string;
  api_key_ref?: string;
  list_args?: string[];
  tui_args?: string[];
  output_path?: string;
  timeout?: number;
  retries?: number;
  max_retries?: number;
  api_path?: string;
  models_path?: string;
  headers?: Record<string, string>;
  temperature?: number;
  max_tokens?: number;
  default_model?: string;
  thinking_mode?: boolean;
  streaming?: boolean;
  sdk_params?: Record<string, any>;
  request_overrides?: Record<string, any>;
  cli_mode?: CLIMode;
  thinking_extraction?: {
    enabled: boolean;
    patterns: string[];
    confidence_threshold: number;
  };
  model_specific?: Record<string, any>;
  [key: string]: any;
}

// Simple Provider (for UI)
export interface SimpleProvider {
  id: string;
  name: string;
  kind: ProviderKind;
  conn: ProviderConnection;
  cliMode?: CLIMode;
  modelId: string;
  status: ProviderStatus;
  lastError?: string;
  lastTest?: {
    at: string;
    latencyMs?: number;
    usage?: { totalTokens?: number; estimated?: boolean };
    note?: string;
  };
  costClass?: CostClass;
  outputPath?: string;
}

// Validation Result
export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  normalized_config?: ProviderConfig;
}

// Role Config
export interface RoleConfig {
  provider_id?: string;
  model?: string;
  profile?: string;
}

// Role Requirements
export interface RoleRequirement {
  requires_thinking?: boolean;
  min_confidence?: number;
  error_message?: string;
}

// LLM Config
export interface LLMConfig {
  schema_version: number;
  providers: Record<string, ProviderConfig>;
  roles: Record<string, RoleConfig>;
  policies?: {
    required_ready_roles?: string[];
    test_required_suites?: string[];
    role_requirements?: Record<string, RoleRequirement>;
  };
}

// LLM Status


// LLM Status Role (Rich)
export interface LLMStatusRole {
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

// LLM Status Provider (Rich)
export interface LLMStatusProvider {
  ready?: boolean | null;
  grade?: string;
  last_run_id?: string | null;
  timestamp?: string | null;
  suites?: Record<string, unknown> | null;
  model?: string | null;
  role?: string | null;
}

// LLM Status (Rich)
export interface LLMStatus {
  state: string;
  required_ready_roles: string[];
  blocked_roles: string[];
  unsupported_roles: string[];
  roles: Record<string, LLMStatusRole>;
  providers?: Record<string, LLMStatusProvider>; // providers might be optional? EnhancedLLMSettingsTab has providers? Record<...>
  last_updated: string;
}

export interface LLMStatusSuite {
  status: 'pass' | 'fail' | 'skip';
  note?: string;
  latency_ms?: number;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    estimated?: boolean;
  };
}

// Provider Settings Props
export interface ProviderSettingsProps {
  providerId?: string;
  provider: {
    type: string;
    name: string;
    command?: string;
    args?: string[];
    env?: Record<string, string>;
    base_url?: string;
    api_key?: string;
    timeout?: number;
    retries?: number;
    temperature?: number;
    max_tokens?: number;
    [key: string]: any;
  };
  onUpdate: (updates: Partial<ProviderConfig>) => void;
  onValidate: () => ValidationResult;
  children?: React.ReactNode;
}

// Utility Types
export interface ProviderLabels {
  [key: string]: string;
}

export interface StatusColors {
  [key: string]: string;
}

export interface StatusBadges {
  [key: string]: string;
}

// Helper Functions
export const isCLIProvider = (kind: ProviderKind): boolean => {
  return kind === PROVIDER_KINDS.CODEX_CLI || kind === PROVIDER_KINDS.GEMINI_CLI;
};

export const isCLIProviderType = (providerType?: string): providerType is CLIConnectionKind => {
  return providerType === PROVIDER_KINDS.CODEX_CLI || providerType === PROVIDER_KINDS.GEMINI_CLI;
};

export const requiresApiKeyForType = (providerType?: string): boolean => {
  if (!providerType) return true;
  if (providerType === PROVIDER_KINDS.OLLAMA) return false;
  return !isCLIProviderType(providerType);
};

export const usesBaseUrlForType = (providerType?: string): boolean => {
  return (
    providerType === PROVIDER_KINDS.CODEX_SDK ||
    providerType === PROVIDER_KINDS.OPENAI_COMPAT ||
    providerType === PROVIDER_KINDS.ANTHROPIC_COMPAT ||
    providerType === PROVIDER_KINDS.MAXMINI ||
    providerType === PROVIDER_KINDS.GEMINI_API
  );
};

export const isAPIProvider = (kind: ProviderKind): boolean => {
  return !isCLIProvider(kind);
};

export const isCodexCLIProvider = (kind: ProviderKind, conn?: ProviderConnection): boolean => {
  if (kind === PROVIDER_KINDS.CODEX_CLI) return true;
  if (kind === PROVIDER_KINDS.GEMINI_CLI && conn && 
      (conn.kind === 'gemini_cli' || conn.kind === 'codex_cli') &&
      conn.command.toLowerCase().includes('codex')) {
    return true;
  }
  return false;
};

export const isGeminiCLIProvider = (kind: ProviderKind, conn?: ProviderConnection): boolean => {
  if (kind === PROVIDER_KINDS.GEMINI_CLI) return true;
  if (kind === PROVIDER_KINDS.CODEX_CLI && conn && 
      (conn.kind === 'codex_cli' || conn.kind === 'gemini_cli') &&
      conn.command.toLowerCase().includes('gemini')) {
    return true;
  }
  return false;
};

export const isAgentProvider = (info: ProviderInfo): boolean => {
  return info.provider_category === PROVIDER_CATEGORIES.AGENT;
};

export const isLLMProvider = (info: ProviderInfo): boolean => {
  return info.provider_category === PROVIDER_CATEGORIES.LLM;
};

export const requiresAPIKey = (kind: ProviderKind): boolean => {
  return !isCLIProvider(kind);
};

export const supportsTUI = (kind: ProviderKind): boolean => {
  return isCLIProvider(kind);
};

export const supportsAPIListing = (kind: ProviderKind): boolean => {
  return isAPIProvider(kind);
};

// Connection type helpers
export const isCLIConnection = (conn: ProviderConnection): conn is CLIConnection => {
  return conn.kind === 'codex_cli' || conn.kind === 'gemini_cli';
};

export const isHTTPConnection = (conn: ProviderConnection): conn is HTTPConnection => {
  return conn.kind === 'http';
};

// Provider Classification Constants
export const PROVIDER_LABELS: ProviderLabels = {
  [PROVIDER_KINDS.CODEX_CLI]: 'Codex CLI',
  [PROVIDER_KINDS.CODEX_SDK]: 'Codex SDK',
  [PROVIDER_KINDS.GEMINI_CLI]: 'Gemini CLI',
  [PROVIDER_KINDS.OLLAMA]: 'Ollama',
  [PROVIDER_KINDS.OPENAI_COMPAT]: 'OpenAI',
  [PROVIDER_KINDS.ANTHROPIC_COMPAT]: 'Anthropic-compatible',
  [PROVIDER_KINDS.CUSTOM_HTTPS]: 'Custom HTTPS',
  [PROVIDER_KINDS.MAXMINI]: 'MiniMax',
  [PROVIDER_KINDS.GEMINI_API]: 'Gemini API'
};

export const STATUS_COLORS: StatusColors = {
  [PROVIDER_STATUS.UNTESTED]: 'text-gray-400',
  [PROVIDER_STATUS.TESTING]: 'text-blue-400',
  [PROVIDER_STATUS.READY]: 'text-emerald-400',
  [PROVIDER_STATUS.FAILED]: 'text-red-400'
};

export const STATUS_BADGES: StatusBadges = {
  [PROVIDER_STATUS.UNTESTED]: 'bg-gray-500/20 text-gray-300 border-gray-500/30',
  [PROVIDER_STATUS.TESTING]: 'bg-blue-500/20 text-blue-200 border-blue-500/30 animate-pulse',
  [PROVIDER_STATUS.READY]: 'bg-emerald-500/20 text-emerald-200 border-emerald-500/30',
  [PROVIDER_STATUS.FAILED]: 'bg-red-500/20 text-red-200 border-red-500/30'
};
