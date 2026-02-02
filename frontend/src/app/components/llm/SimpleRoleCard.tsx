import { 
  CheckCircle2, 
  AlertTriangle, 
  Loader2, 
  PlayCircle, 
  ChevronDown,
  Settings
} from 'lucide-react';
import { useState } from 'react';
import type { SimpleProvider } from './SimpleModelCard';

export interface SimpleRole {
  role: 'pm' | 'director' | 'qa' | 'docs';
  providerId?: string;
  status: 'unconfigured' | 'ready' | 'failed' | 'degraded';
  lastTest?: {
    at: string;
    result: 'pass' | 'fail';
    reason?: string;
  };
}

interface SimpleRoleCardProps {
  role: SimpleRole;
  availableProviders: SimpleProvider[];
  onUpdate: (updates: Partial<SimpleRole>) => void;
  onTestRole: () => Promise<void>;
  onViewTestReport?: () => void;
}

const ROLE_META = {
  pm: { 
    label: 'PM', 
    color: 'text-cyan-300', 
    badge: 'bg-cyan-500/20 text-cyan-200 border-cyan-500/30',
    description: 'Project Management - Coordinates tasks and manages workflow'
  },
  director: { 
    label: 'Director', 
    color: 'text-purple-300', 
    badge: 'bg-purple-500/20 text-purple-200 border-purple-500/30',
    description: 'Creative Director - Oversees design and creative direction'
  },
  qa: { 
    label: 'QA', 
    color: 'text-blue-200', 
    badge: 'bg-blue-500/20 text-blue-200 border-blue-500/30',
    description: 'Quality Assurance - Reviews and validates work quality'
  },
  docs: { 
    label: 'Docs', 
    color: 'text-emerald-300', 
    badge: 'bg-emerald-500/20 text-emerald-200 border-emerald-500/30',
    description: 'Documentation - Creates and maintains documentation'
  },
};

const STATUS_COLORS = {
  unconfigured: 'text-gray-400',
  ready: 'text-emerald-400',
  failed: 'text-red-400',
  degraded: 'text-amber-400'
};

const STATUS_BADGES = {
  unconfigured: 'bg-gray-500/20 text-gray-300 border-gray-500/30',
  ready: 'bg-emerald-500/20 text-emerald-200 border-emerald-500/30',
  failed: 'bg-red-500/20 text-red-200 border-red-500/30',
  degraded: 'bg-amber-500/20 text-amber-200 border-amber-500/30'
};

const ROLE_TEST_DESCRIPTIONS = {
  pm: 'Tests structured task output + acceptance criteria (JSON parsing)',
  director: 'Tests evidence list output (no direct patch writing)',
  qa: 'Tests mandatory PASS/FAIL output with reasoning',
  docs: 'Tests template-based generation (no hallucination)'
};

export function SimpleRoleCard({
  role,
  availableProviders,
  onUpdate,
  onTestRole,
  onViewTestReport
}: SimpleRoleCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isTesting, setIsTesting] = useState(false);

  const meta = ROLE_META[role.role];
  const readyProviders = availableProviders.filter(p => p.status === 'ready');
  const selectedProvider = availableProviders.find(p => p.id === role.providerId);

  const handleProviderChange = (providerId: string) => {
    onUpdate({ providerId, status: 'unconfigured' });
  };

  const handleTestRole = async () => {
    setIsTesting(true);
    try {
      await onTestRole();
    } finally {
      setIsTesting(false);
    }
  };

  const renderStatusIndicator = () => {
    switch (role.status) {
      case 'ready':
        return <CheckCircle2 className="size-4 text-emerald-400" />;
      case 'failed':
        return <AlertTriangle className="size-4 text-red-400" />;
      case 'degraded':
        return <AlertTriangle className="size-4 text-amber-400" />;
      default:
        return <div className="size-4 rounded-full bg-gray-500/60" />;
    }
  };

  const renderCompactView = () => (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {renderStatusIndicator()}
          <div>
            <h4 className="text-sm font-semibold text-text-main">{meta.label}</h4>
            <p className="text-[10px] text-text-dim">{meta.description}</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={handleTestRole}
            disabled={isTesting || !role.providerId || role.status === 'degraded'}
            className="px-3 py-1.5 text-[10px] font-semibold bg-purple-500/80 hover:bg-purple-500 text-white rounded transition-colors disabled:opacity-60 flex items-center gap-1"
          >
            {isTesting ? (
              <Loader2 className="size-3 animate-spin" />
            ) : (
              <PlayCircle className="size-3" />
            )}
            Test Role
          </button>
          
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 rounded border border-white/10 hover:border-accent/40 transition-colors"
          >
            {isExpanded ? <ChevronDown className="size-3 rotate-180" /> : <ChevronDown className="size-3" />}
          </button>
        </div>
      </div>

      {/* Provider Selection */}
      <div className="flex items-center gap-3">
        <label className="text-xs text-text-muted">Model:</label>
        <select
          value={role.providerId || ''}
          onChange={(e) => handleProviderChange(e.target.value)}
          disabled={readyProviders.length === 0}
          className="flex-1 bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/50 disabled:opacity-60"
        >
          <option value="">Select a model...</option>
          {readyProviders.map(provider => (
            <option key={provider.id} value={provider.id}>
              {provider.name} ({provider.modelId})
            </option>
          ))}
        </select>
      </div>

      {/* Status Messages */}
      {readyProviders.length === 0 && (
        <div className="text-[10px] text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded p-2">
          No ready models available. Configure and test models in Step 1 first.
        </div>
      )}

      {role.status === 'degraded' && selectedProvider && (
        <div className="text-[10px] text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded p-2">
          Assigned model "{selectedProvider.name}" is no longer ready. 
          Go to Step 1 to fix the model or select a different model.
        </div>
      )}

      {role.status === 'failed' && role.lastTest?.reason && (
        <div className="text-[10px] text-red-400 bg-red-500/10 border border-red-500/20 rounded p-2">
          Role test failed: {role.lastTest.reason}
        </div>
      )}
    </div>
  );

  const renderExpandedView = () => (
    <div className="space-y-4 pt-4 border-t border-white/10">
      {/* Selected Provider Details */}
      {selectedProvider && (
        <div className="space-y-3">
          <h5 className="text-xs font-semibold text-text-main">Selected Model</h5>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-text-muted">Name:</span>
              <span className="text-text-main">{selectedProvider.name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Type:</span>
              <span className="text-text-main capitalize">{selectedProvider.kind}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Model ID:</span>
              <span className="text-text-main font-mono">{selectedProvider.modelId}</span>
            </div>
            {selectedProvider.lastTest?.latencyMs && (
              <div className="flex justify-between">
                <span className="text-text-muted">Latency:</span>
                <span className="text-text-main">{selectedProvider.lastTest.latencyMs}ms</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Role Test Details */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Role Test</h5>
        <div className="text-xs text-text-dim">
          {ROLE_TEST_DESCRIPTIONS[role.role]}
        </div>
        
        {role.lastTest && (
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-text-muted">Last Test:</span>
              <span className="text-text-main">{new Date(role.lastTest.at).toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Result:</span>
              <span className={`font-semibold ${
                role.lastTest.result === 'pass' ? 'text-emerald-400' : 'text-red-400'
              }`}>
                {role.lastTest.result.toUpperCase()}
              </span>
            </div>
            {role.lastTest.reason && (
              <div className="text-text-main">{role.lastTest.reason}</div>
            )}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 pt-3 border-t border-white/10">
        <button
          onClick={handleTestRole}
          disabled={isTesting || !role.providerId || role.status === 'degraded'}
          className="px-3 py-1.5 text-[10px] font-semibold bg-purple-500/80 hover:bg-purple-500 text-white rounded transition-colors disabled:opacity-60 flex items-center gap-1"
        >
          {isTesting ? (
            <Loader2 className="size-3 animate-spin" />
          ) : (
            <PlayCircle className="size-3" />
          )}
          Test Role
        </button>
        
        {onViewTestReport && role.lastTest && (
          <button
            onClick={onViewTestReport}
            className="px-3 py-1.5 text-[10px] border border-white/10 rounded hover:border-accent/40 flex items-center gap-1"
          >
            <Settings className="size-3" />
            View Report
          </button>
        )}
      </div>
    </div>
  );

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10 hover:border-white/20 transition-all">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-1 text-[10px] uppercase font-semibold rounded border ${meta.badge}`}>
            {meta.label}
          </span>
          <span className={`px-2 py-1 text-[10px] uppercase font-semibold rounded border ${STATUS_BADGES[role.status]}`}>
            {role.status.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Content */}
      <>
        {renderCompactView()}
        {isExpanded && renderExpandedView()}
      </>
    </div>
  );
}
