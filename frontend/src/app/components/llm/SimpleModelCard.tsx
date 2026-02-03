import { 
  CheckCircle2, 
  AlertTriangle, 
  Loader2, 
  PlayCircle, 
  Eye, 
  EyeOff, 
  Trash2, 
  Edit3, 
  ChevronDown, 
  ChevronUp,
  Terminal
} from 'lucide-react';
import { useState } from 'react';
import {
  PROVIDER_LABELS,
  STATUS_BADGES,
  isCLIProvider,
  isCodexCLIProvider,
  isCLIConnection,
  isHTTPConnection,
  type ProviderKind,
  type SimpleProvider
} from './types';

interface SimpleModelCardProps {
  provider: SimpleProvider;
  onUpdate: (updates: Partial<SimpleProvider>) => void;
  onDelete: () => void;
  onTest: () => void;
  onOpenTuiBrowser?: () => void;
  onViewTestReport?: () => void;
}

const CODEX_EXEC_PRESET = [
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

const CODEX_SLASH_COMMANDS = [
  '/permissions',
  '/apps',
  '/compact',
  '/diff',
  '/exit',
  '/feedback',
  '/init',
  '/logout',
  '/mcp',
  '/mention',
  '/model',
  '/ps',
  '/fork',
  '/resume',
  '/new',
  '/quit',
  '/review',
  '/status'
];

export function SimpleModelCard({
  provider,
  onUpdate,
  onDelete,
  onTest,
  onOpenTuiBrowser,
  onViewTestReport
}: SimpleModelCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [editForm, setEditForm] = useState<SimpleProvider>(provider);
  const [advancedJson, setAdvancedJson] = useState('{}');

  const isCodexCli = isCodexCLIProvider(provider.kind, provider.conn);
  const cliMode = provider.cliMode || 'headless';

  const usesOutputPath =
    isCLIConnection(provider.conn) &&
    (provider.conn.args || []).some((arg: string) => arg.includes('{output}'));

  const applyCodexPreset = () => {
    setEditForm((prev) => ({
      ...prev,
      name: prev.name && prev.name.trim() ? prev.name : 'Codex CLI',
      kind: 'codex_cli',
      cliMode: 'headless',
      conn: {
        kind: 'codex_cli',
        command: 'codex',
        args: CODEX_EXEC_PRESET,
        env: (prev.conn.kind === 'codex_cli' || prev.conn.kind === 'gemini_cli') ? prev.conn.env : {}
      }
    }));
  };

  const handleSaveEdit = () => {
    onUpdate(editForm);
    setIsEditing(false);
  };

  const handleCancelEdit = () => {
    setEditForm(provider);
    setIsEditing(false);
  };

  const renderStatusIndicator = () => {
    switch (provider.status) {
      case 'ready':
        return <CheckCircle2 className="size-4 text-emerald-400" />;
      case 'testing':
        return <Loader2 className="size-4 text-blue-400 animate-spin" />;
      case 'failed':
        return <AlertTriangle className="size-4 text-red-400" />;
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
            <h4 className="text-sm font-semibold text-text-main">{provider.name}</h4>
            <div className="flex items-center gap-2 text-[10px] text-text-dim">
              <span className="capitalize">{PROVIDER_LABELS[provider.kind]}</span>
              <span>•</span>
              <span className="font-mono">{provider.modelId || "default"}</span>
              {provider.costClass && (
                <>
                  <span>•</span>
                  <span className="text-amber-400">{provider.costClass}</span>
                </>
              )}
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={onTest}
            disabled={provider.status === 'testing'}
            className="px-3 py-1.5 text-[10px] font-semibold bg-cyan-500/80 hover:bg-cyan-500 text-white rounded transition-colors disabled:opacity-60 flex items-center gap-1"
          >
            {provider.status === 'testing' ? (
              <Loader2 className="size-3 animate-spin" />
            ) : (
              <PlayCircle className="size-3" />
            )}
            Test
          </button>
          
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 rounded border border-white/10 hover:border-accent/40 transition-colors"
          >
            {isExpanded ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
          </button>
        </div>
      </div>

      {provider.lastError && (
        <div className="text-[10px] text-red-400 bg-red-500/10 border border-red-500/20 rounded p-2">
          {provider.lastError}
        </div>
      )}
    </div>
  );

  const renderExpandedView = () => (
    <div className="space-y-4 pt-4 border-t border-white/10">
      {/* Connection Details */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Connection Details</h5>
        
        {isCLIConnection(provider.conn) ? (
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-text-muted">Command:</span>
              <span className="text-text-main font-mono">{provider.conn.command}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Args:</span>
              <span className="text-text-main font-mono">{(provider.conn.args || []).join(' ')}</span>
            </div>
            {provider.conn.env && Object.keys(provider.conn.env).length > 0 && (
              <div className="flex justify-between">
                <span className="text-text-muted">Environment:</span>
                <span className="text-text-main font-mono">{Object.keys(provider.conn.env).join(', ')}</span>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-text-muted">Base URL:</span>
              <span className="text-text-main font-mono">
                {isHTTPConnection(provider.conn) ? provider.conn.baseUrl : ''}
              </span>
            </div>
            {isHTTPConnection(provider.conn) && provider.conn.apiKey && (
              <div className="flex justify-between">
                <span className="text-text-muted">API Key:</span>
                <span className="text-text-main">•••••••••••••••</span>
              </div>
            )}
          </div>
        )}
      </div>

      {isCodexCli && cliMode === 'headless' && (
        <div className="space-y-2 text-xs">
          <h5 className="text-xs font-semibold text-text-main">Codex CLI Headless Template</h5>
          <div className="text-[10px] text-text-dim">推荐 exec 参数（JSON 输出，适合自动化测试）</div>
          <div className="text-[10px] font-mono text-text-main bg-black/30 rounded px-2 py-1 border border-white/10">
            {CODEX_EXEC_PRESET.join(' ')}
          </div>
        </div>
      )}

      {isCodexCli && cliMode === 'tui' && (
        <div className="space-y-2 text-xs">
          <h5 className="text-xs font-semibold text-text-main">Codex CLI TUI 快速参考</h5>
          <div className="text-[10px] text-text-dim">TUI Slash Commands：</div>
          <div className="text-[10px] text-text-main font-mono">
            {CODEX_SLASH_COMMANDS.join(' ')}
          </div>
          <div className="text-[9px] text-text-dim">{'\u5b9e\u9645\u53ef\u7528\u547d\u4ee4\u4ee5 Codex CLI \u7684 / \u5217\u8868\u4e3a\u51c6\uff0c/approvals \u4ecd\u53ef\u4f5c\u4e3a /permissions \u7684\u522b\u540d\u3002'}</div>
        </div>
      )}

      {/* Test Results */}
      {provider.lastTest && (
        <div className="space-y-3">
          <h5 className="text-xs font-semibold text-text-main">Last Test</h5>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-text-muted">Time:</span>
              <span className="text-text-main">{new Date(provider.lastTest.at).toLocaleString()}</span>
            </div>
            {provider.lastTest.latencyMs && (
              <div className="flex justify-between">
                <span className="text-text-muted">Latency:</span>
                <span className="text-text-main">{provider.lastTest.latencyMs}ms</span>
              </div>
            )}
            {provider.lastTest.usage && (
              <div className="flex justify-between">
                <span className="text-text-muted">Tokens:</span>
                <span className="text-text-main">
                  {provider.lastTest.usage.totalTokens} {provider.lastTest.usage.estimated ? '(est.)' : ''}
                </span>
              </div>
            )}
            {provider.lastTest.note && (
              <div className="text-text-main">{provider.lastTest.note}</div>
            )}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-3 border-t border-white/10">
        <button
          onClick={onTest}
          disabled={provider.status === 'testing'}
          className="px-3 py-1.5 text-[10px] border border-white/10 rounded hover:border-accent/40 disabled:opacity-60 flex items-center gap-1"
        >
          <PlayCircle className="size-3" />
          Test
        </button>
        
        {isCLIConnection(provider.conn) && cliMode === 'tui' && onOpenTuiBrowser && (
          <button
            onClick={onOpenTuiBrowser}
            className="px-3 py-1.5 text-[10px] border border-white/10 rounded hover:border-cyan-400/40 flex items-center gap-1"
          >
            <Terminal className="size-3" />
            TUI Browser
          </button>
        )}
        
        {onViewTestReport && (
          <button
            onClick={onViewTestReport}
            className="px-3 py-1.5 text-[10px] border border-white/10 rounded hover:border-accent/40 flex items-center gap-1"
          >
            <Eye className="size-3" />
            View Report
          </button>
        )}
        
        <button
          onClick={() => setIsEditing(true)}
          className="px-3 py-1.5 text-[10px] border border-white/10 rounded hover:border-accent/40 flex items-center gap-1"
        >
          <Edit3 className="size-3" />
          Edit
        </button>
        
        <button
          onClick={onDelete}
          className="px-3 py-1.5 text-[10px] border border-red-500/30 rounded hover:border-red-500/40 text-red-400 flex items-center gap-1"
        >
          <Trash2 className="size-3" />
          Delete
        </button>
      </div>

      {/* Advanced Options */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Advanced Options</h5>
        <textarea
          value={advancedJson}
          onChange={(e) => setAdvancedJson(e.target.value)}
          placeholder='{"timeout": 60, "retries": 3, "headers": {...}}'
          className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-xs font-mono h-20"
        />
        <p className="text-[9px] text-text-dim">
          JSON overrides for provider-specific settings (timeout, retries, headers, etc.)
        </p>
      </div>
    </div>
  );

  const renderEditView = () => (
    <div className="space-y-4 pt-4 border-t border-white/10">
      <h5 className="text-xs font-semibold text-text-main">Edit Provider</h5>
      
      <div className="space-y-3">
        <div>
          <label className="block text-xs text-text-muted mb-1">Name</label>
          <input
            type="text"
            value={editForm.name}
            onChange={(e) => setEditForm(prev => ({ ...prev, name: e.target.value }))}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
          />
        </div>

        <div>
          <label className="block text-xs text-text-muted mb-1">Type</label>
          <select
            value={editForm.kind}
            onChange={(e) => {
              const newKind = e.target.value as ProviderKind;
              setEditForm(prev => {
                const baseProvider = { ...prev, kind: newKind, cliMode: isCLIProvider(newKind) ? 'headless' : undefined };
                if (newKind === 'codex_cli' || newKind === 'gemini_cli') {
                  return {
                    ...baseProvider,
                    conn: { kind: newKind, command: '', args: [], env: {} }
                  };
                } else {
                  return {
                    ...baseProvider,
                    conn: { kind: 'http', baseUrl: '' }
                  };
                }
              });
            }}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
          >
            <option value="codex_cli">Codex CLI</option>
            <option value="gemini_cli">Gemini CLI</option>
            <option value="ollama">Ollama</option>
            <option value="openai_compat">OpenAI-compatible</option>
            <option value="anthropic_compat">Anthropic-compatible</option>
            <option value="custom_https">Custom HTTPS</option>
          </select>
        </div>

        {isCLIConnection(editForm.conn) ? (
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-text-muted mb-1">CLI Mode</label>
              <select
                value={editForm.cliMode || 'headless'}
                onChange={(e) => setEditForm(prev => ({ ...prev, cliMode: e.target.value as 'tui' | 'headless' }))}
                className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
              >
                <option value="headless">Headless (non-interactive)</option>
                <option value="tui">TUI (interactive)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">Command</label>
              <input
                type="text"
                value={editForm.conn.command}
                onChange={(e) => setEditForm(prev => ({ 
                  ...prev, 
                  conn: { ...prev.conn, kind: editForm.conn.kind, command: e.target.value }
                }) as SimpleProvider)}
                className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
                placeholder="codex, gemini, etc."
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">Args (one per line)</label>
              <textarea
                value={(editForm.conn.args || []).join('\n')}
                onChange={(e) => setEditForm(prev => ({ 
                  ...prev, 
                  conn: { ...prev.conn, kind: editForm.conn.kind, args: e.target.value.split('\n').filter(Boolean) }
                }) as SimpleProvider)}
                className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono h-16"
              />
            </div>
            {usesOutputPath && (
              <div>
                <label className="block text-xs text-text-muted mb-1">Output Path (optional)</label>
                <input
                  type="text"
                  value={editForm.outputPath || ""}
                  onChange={(e) => setEditForm(prev => ({ ...prev, outputPath: e.target.value }))}
                  className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
                  placeholder=".harborpilot/runtime/CODEX_LAST_MESSAGE.md"
                />
                <p className="text-[9px] text-text-dim mt-1">仅当 args 中包含 {`{output}`} 时才会写入。</p>
              </div>
            )}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={applyCodexPreset}
                className="px-3 py-1.5 text-[10px] border border-emerald-500/30 rounded hover:border-emerald-400/60 text-emerald-200"
              >
                应用 Codex CLI 预设
              </button>
              <span className="text-[9px] text-text-dim">推荐用于 codex exec + 面试测试</span>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-text-muted mb-1">Base URL</label>
              <input
                type="text"
                value={isHTTPConnection(editForm.conn) ? editForm.conn.baseUrl : ''}
                onChange={(e) => setEditForm(prev => ({ 
                  ...prev, 
                  conn: { ...prev.conn, kind: 'http', baseUrl: e.target.value }
                }) as SimpleProvider)}
                className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
                placeholder="https://api.example.com/v1"
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">API Key</label>
              <div className="flex items-center gap-2">
                <input
                  type={showApiKey ? "text" : "password"}
                  value={isHTTPConnection(editForm.conn) ? editForm.conn.apiKey || '' : ''}
                  onChange={(e) => setEditForm(prev => ({ 
                    ...prev, 
                    conn: { ...prev.conn, kind: 'http', apiKey: e.target.value }
                  }) as SimpleProvider)}
                  className="flex-1 bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
                  placeholder="Enter your API key"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="p-2 rounded border border-white/10 hover:border-accent/40"
                >
                  {showApiKey ? <EyeOff className="size-3" /> : <Eye className="size-3" />}
                </button>
              </div>
            </div>
          </div>
        )}

        <div>
          <label className="block text-xs text-text-muted mb-1">Model ID</label>
          <input
            type="text"
            value={editForm.modelId}
            onChange={(e) => setEditForm(prev => ({ ...prev, modelId: e.target.value }))}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
            placeholder="gpt-4, claude-3-5-sonnet, etc."
          />
        </div>
      </div>

      <div className="flex items-center gap-2 pt-3 border-t border-white/10">
        <button
          onClick={handleSaveEdit}
          className="px-3 py-1.5 text-[10px] font-semibold bg-accent/80 hover:bg-accent text-white rounded transition-colors"
        >
          Save
        </button>
        <button
          onClick={handleCancelEdit}
          className="px-3 py-1.5 text-[10px] border border-white/10 rounded hover:border-accent/40"
        >
          Cancel
        </button>
      </div>
    </div>
  );

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10 hover:border-white/20 transition-all">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-1 text-[10px] uppercase font-semibold rounded border ${STATUS_BADGES[provider.status]}`}>
            {provider.status.toUpperCase()}
          </span>
          <span className="text-[10px] text-text-dim capitalize">
            {PROVIDER_LABELS[provider.kind]}
          </span>
          {isCodexCli && (
            <span className="px-2 py-1 text-[9px] uppercase font-semibold rounded border bg-emerald-500/10 text-emerald-200 border-emerald-500/30">
              Codex CLI
            </span>
          )}
        </div>
      </div>

      {/* Content */}
      {isEditing ? renderEditView() : (
        <>
          {renderCompactView()}
          {isExpanded && renderExpandedView()}
        </>
      )}
    </div>
  );
}
