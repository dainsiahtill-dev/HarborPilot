import { Loader2, CheckCircle2, AlertTriangle, Plus, PlayCircle, Save } from 'lucide-react';
import { useState } from 'react';
import { SimpleModelCard, SimpleProvider, ProviderKind } from './SimpleModelCard';
import { SimpleRoleCard, SimpleRole } from './SimpleRoleCard';

interface LlmConfig {
  schema_version: number;
  providers: Record<string, any>;
  roles: Record<string, any>;
  policies?: {
    required_ready_roles?: string[];
    test_required_suites?: string[];
  };
}

interface LlmStatus {
  state: string;
  required_ready_roles: string[];
  blocked_roles: string[];
  unsupported_roles: string[];
  roles: Record<string, any>;
}

interface LLMSettingsTabProps {
  llmConfig: LlmConfig | null;
  llmStatus: LlmStatus | null;
  llmLoading: boolean;
  llmSaving: boolean;
  llmError: string | null;
  onSaveConfig: () => void;
  onTestModel: (providerId: string, level: 'quick' | 'deep') => Promise<void>;
  onTestRole: (role: string) => Promise<void>;
  onOpenTuiBrowser: (providerId: string) => void;
  onViewTestReport: (type: 'model' | 'role', id: string) => void;
}

interface LLMSettingsTabSimplifiedProps {
  llmConfig: LlmConfig | null;
  llmStatus: LlmStatus | null;
  llmLoading: boolean;
  llmSaving: boolean;
  llmError: string | null;
  onSaveConfig: () => void;
  onTestModel: (providerId: string, level: 'quick' | 'deep') => Promise<void>;
  onTestRole: (role: string) => Promise<void>;
  onOpenTuiBrowser: (providerId: string) => void;
  onViewTestReport: (type: 'model' | 'role', id: string) => void;
}

const DEFAULT_PROVIDERS: SimpleProvider[] = [
  {
    id: 'codex-cli',
    name: 'Codex CLI',
    kind: 'cli',
    conn: { kind: 'cli', command: 'codex', args: [], env: {} },
    modelId: '',
    status: 'untested',
    costClass: 'LOCAL'
  },
  {
    id: 'ollama-local',
    name: 'Ollama Local',
    kind: 'ollama',
    conn: { kind: 'http', baseUrl: 'http://127.0.0.1:11434' },
    modelId: '',
    status: 'untested',
    costClass: 'LOCAL'
  },
  {
    id: 'openai-gpt4',
    name: 'OpenAI GPT-4',
    kind: 'openai_compat',
    conn: { kind: 'http', baseUrl: 'https://api.openai.com/v1' },
    modelId: 'gpt-4',
    status: 'untested',
    costClass: 'METERED'
  }
];

const DEFAULT_ROLES: SimpleRole[] = [
  { role: 'pm', status: 'unconfigured' },
  { role: 'director', status: 'unconfigured' },
  { role: 'qa', status: 'unconfigured' },
  { role: 'docs', status: 'unconfigured' }
];

export function LLMSettingsTab(props: LLMSettingsTabProps) {
  // Use the simplified implementation
  return <LLMSettingsTabSimplified {...props} />;
}

export function LLMSettingsTabSimplified({
  llmConfig,
  llmStatus,
  llmLoading,
  llmSaving,
  llmError,
  onSaveConfig,
  onTestModel,
  onTestRole,
  onOpenTuiBrowser,
  onViewTestReport
}: LLMSettingsTabSimplifiedProps) {
  const [providers, setProviders] = useState<SimpleProvider[]>(DEFAULT_PROVIDERS);
  const [roles, setRoles] = useState<SimpleRole[]>(DEFAULT_ROLES);
  const [isAddingProvider, setIsAddingProvider] = useState(false);
  const [newProvider, setNewProvider] = useState<SimpleProvider>({
    id: '',
    name: '',
    kind: 'openai_compat',
    conn: { kind: 'http', baseUrl: '' },
    modelId: '',
    status: 'untested'
  });

  // Convert legacy config to simplified format
  useState(() => {
    if (llmConfig) {
      const convertedProviders: SimpleProvider[] = Object.entries(llmConfig.providers || {}).map(([id, config]) => ({
        id,
        name: config.name || id,
        kind: config.type as ProviderKind,
        conn: config.type === 'cli' 
          ? { kind: 'cli' as const, command: config.command || '', args: config.args || [], env: config.env || {} }
          : { kind: 'http' as const, baseUrl: config.base_url || '', apiKey: config.api_key_ref },
        modelId: '',
        status: 'untested',
        costClass: config.type === 'cli' ? 'LOCAL' : config.type === 'ollama' ? 'LOCAL' : 'METERED'
      }));

      const convertedRoles: SimpleRole[] = DEFAULT_ROLES.map(defaultRole => {
        const roleConfig = llmConfig.roles?.[defaultRole.role];
        return {
          role: defaultRole.role,
          providerId: roleConfig?.provider_id,
          status: 'unconfigured'
        };
      });

      setProviders(convertedProviders);
      setRoles(convertedRoles);
    }
  });

  const handleAddProvider = () => {
    if (!newProvider.id.trim() || !newProvider.name.trim()) return;

    const providerToAdd: SimpleProvider = {
      ...newProvider,
      id: newProvider.id.trim(),
      name: newProvider.name.trim(),
      status: 'untested'
    };

    setProviders(prev => [...prev, providerToAdd]);
    setNewProvider({
      id: '',
      name: '',
      kind: 'openai_compat',
      conn: { kind: 'http', baseUrl: '' },
      modelId: '',
      status: 'untested'
    });
    setIsAddingProvider(false);
  };

  const handleUpdateProvider = (providerId: string, updates: Partial<SimpleProvider>) => {
    setProviders(prev => prev.map(p => 
      p.id === providerId ? { ...p, ...updates } : p
    ));
  };

  const handleDeleteProvider = (providerId: string) => {
    setProviders(prev => prev.filter(p => p.id !== providerId));
    // Remove from roles if assigned
    setRoles(prev => prev.map(r => 
      r.providerId === providerId ? { ...r, providerId: undefined, status: 'unconfigured' } : r
    ));
  };

  const handleUpdateRole = (roleId: string, updates: Partial<SimpleRole>) => {
    setRoles(prev => prev.map(r => 
      r.role === roleId ? { ...r, ...updates } : r
    ));
  };

  const handleTestModel = async (providerId: string, level: 'quick' | 'deep') => {
    // Update status to testing
    handleUpdateProvider(providerId, { status: 'testing' });
    
    try {
      await onTestModel(providerId, level);
      handleUpdateProvider(providerId, { 
        status: 'ready',
        lastTest: {
          at: new Date().toISOString(),
          note: `${level} test completed successfully`
        }
      });
    } catch (error) {
      handleUpdateProvider(providerId, { 
        status: 'failed',
        lastError: error instanceof Error ? error.message : 'Test failed',
        lastTest: {
          at: new Date().toISOString(),
          note: `${level} test failed`
        }
      });
    }
  };

  const handleTestRole = async (roleId: string) => {
    const role = roles.find(r => r.role === roleId);
    if (!role?.providerId) return;

    // Update status to testing
    handleUpdateRole(roleId, { status: 'failed' }); // Temporary status during test
    
    try {
      await onTestRole(roleId);
      handleUpdateRole(roleId, { 
        status: 'ready',
        lastTest: {
          at: new Date().toISOString(),
          result: 'pass'
        }
      });
    } catch (error) {
      handleUpdateRole(roleId, { 
        status: 'failed',
        lastTest: {
          at: new Date().toISOString(),
          result: 'fail',
          reason: error instanceof Error ? error.message : 'Role test failed'
        }
      });
    }
  };

  const handleTestAllModels = async () => {
    for (const provider of providers) {
      if (provider.status !== 'ready') {
        await handleTestModel(provider.id, 'quick');
      }
    }
  };

  const handleTestAllRoles = async () => {
    for (const role of roles) {
      if (role.providerId && role.status !== 'ready') {
        await handleTestRole(role.role);
      }
    }
  };

  const getGlobalReadiness = () => {
    const readyProviders = providers.filter(p => p.status === 'ready').length;
    const readyRoles = roles.filter(r => r.status === 'ready').length;
    const requiredRoles = llmConfig?.policies?.required_ready_roles || ['pm', 'director', 'qa', 'docs'];
    
    if (readyRoles >= requiredRoles.length && readyProviders > 0) {
      return { state: 'READY', color: 'text-emerald-400', badge: 'bg-emerald-500/20 text-emerald-200 border-emerald-500/30' };
    } else if (readyProviders > 0) {
      return { state: 'PARTIAL', color: 'text-amber-400', badge: 'bg-amber-500/20 text-amber-200 border-amber-500/30' };
    } else {
      return { state: 'NOT_READY', color: 'text-red-400', badge: 'bg-red-500/20 text-red-200 border-red-500/30' };
    }
  };

  const globalReadiness = getGlobalReadiness();

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
      {/* Header */}
      <div className="bg-white/5 rounded-xl p-4 border border-white/5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-text-main mb-1">LLM Configuration</h3>
            <p className="text-[10px] text-text-dim">
              Step 1: Configure models • Step 2: Assign roles
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 className={`size-4 ${globalReadiness.color}`} />
              <span className={`text-[10px] uppercase tracking-wider px-2 py-1 rounded border border-white/10 bg-black/30 ${globalReadiness.color}`}>
                {globalReadiness.state}
              </span>
            </div>
            
            <button
              onClick={onSaveConfig}
              disabled={llmSaving}
              className="px-3 py-1.5 text-[10px] font-semibold bg-accent/80 hover:bg-accent text-white rounded transition-colors disabled:opacity-60 flex items-center gap-1"
            >
              {llmSaving ? <Loader2 className="size-3 animate-spin" /> : <Save className="size-3" />}
              Save Config
            </button>
          </div>
        </div>

        {llmError ? (
          <div className="mt-3 text-xs text-status-error bg-status-error/10 border border-status-error/20 rounded p-2">
            {llmError}
          </div>
        ) : null}
      </div>

      {/* Step 1: Model Configuration */}
      <div className="bg-white/5 rounded-xl p-4 border border-white/5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-text-main">Step 1: Model Configuration</h3>
            <p className="text-[10px] text-text-dim">Add and test your LLM models</p>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={handleTestAllModels}
              className="px-3 py-1.5 text-[10px] border border-white/10 rounded hover:border-cyan-400/40 flex items-center gap-1"
            >
              <PlayCircle className="size-3" />
              Test All Models
            </button>
            
            <button
              onClick={() => setIsAddingProvider(true)}
              className="px-3 py-1.5 text-[10px] font-semibold bg-cyan-500/80 hover:bg-cyan-500 text-white rounded transition-colors flex items-center gap-1"
            >
              <Plus className="size-3" />
              Add Model
            </button>
          </div>
        </div>

        {/* Add New Provider Form */}
        {isAddingProvider && (
          <div className="bg-black/20 rounded-lg p-4 mb-4 border border-white/10">
            <h4 className="text-xs font-semibold text-text-main mb-3">Add New Model</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <input
                type="text"
                placeholder="Model ID (e.g., claude-3-5-sonnet)"
                value={newProvider.id}
                onChange={(e) => setNewProvider(prev => ({ ...prev, id: e.target.value }))}
                className="bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
              />
              <input
                type="text"
                placeholder="Display Name (e.g., Claude 3.5)"
                value={newProvider.name}
                onChange={(e) => setNewProvider(prev => ({ ...prev, name: e.target.value }))}
                className="bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
              />
              <select
                value={newProvider.kind}
                onChange={(e) => setNewProvider(prev => ({ 
                  ...prev, 
                  kind: e.target.value as ProviderKind,
                  conn: e.target.value === 'cli' ? 
                    { kind: 'cli' as const, command: '', args: [], env: {} } :
                    { kind: 'http' as const, baseUrl: '' }
                }))}
                className="bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
              >
                <option value="cli">CLI</option>
                <option value="ollama">Ollama</option>
                <option value="openai_compat">OpenAI-compatible</option>
                <option value="custom_https">Custom HTTPS</option>
              </select>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleAddProvider}
                  disabled={!newProvider.id.trim() || !newProvider.name.trim()}
                  className="px-3 py-1.5 text-[10px] font-semibold bg-accent/80 hover:bg-accent text-white rounded transition-colors disabled:opacity-60"
                >
                  Add
                </button>
                <button
                  onClick={() => setIsAddingProvider(false)}
                  className="px-3 py-1.5 text-[10px] border border-white/10 rounded hover:border-accent/40"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Model Cards */}
        <div className="space-y-4">
          {providers.map(provider => (
            <SimpleModelCard
              key={provider.id}
              provider={provider}
              onUpdate={(updates) => handleUpdateProvider(provider.id, updates)}
              onDelete={() => handleDeleteProvider(provider.id)}
              onTest={(level) => handleTestModel(provider.id, level)}
              onOpenTuiBrowser={() => onOpenTuiBrowser(provider.id)}
              onViewTestReport={() => onViewTestReport('model', provider.id)}
            />
          ))}
        </div>
      </div>

      {/* Step 2: Role Assignment */}
      <div className="bg-white/5 rounded-xl p-4 border border-white/5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-text-main">Step 2: Role Assignment</h3>
            <p className="text-[10px] text-text-dim">Assign tested models to roles</p>
          </div>
          
          <button
            onClick={handleTestAllRoles}
            className="px-3 py-1.5 text-[10px] border border-white/10 rounded hover:border-purple-400/40 flex items-center gap-1"
          >
            <PlayCircle className="size-3" />
            Test All Roles
          </button>
        </div>

        {/* Role Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {roles.map(role => (
            <SimpleRoleCard
              key={role.role}
              role={role}
              availableProviders={providers}
              onUpdate={(updates) => handleUpdateRole(role.role, updates)}
              onTestRole={() => handleTestRole(role.role)}
              onViewTestReport={() => onViewTestReport('role', role.role)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
