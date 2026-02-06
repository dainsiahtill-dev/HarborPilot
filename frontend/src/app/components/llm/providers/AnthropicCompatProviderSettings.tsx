import React from 'react';
import { BaseProviderSettings } from './BaseProviderSettings';
import { type ProviderConfig } from '../types';

const cyberInputClasses = "flex h-9 w-full min-w-0 rounded-md border border-white/10 bg-black/40 px-3 py-1 text-sm text-slate-100 placeholder:text-slate-500 transition-all duration-200 outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 focus:bg-black/60 hover:border-violet-400/30 hover:bg-black/50 disabled:opacity-50 disabled:cursor-not-allowed";

const cyberTextareaClasses = "w-full min-w-0 rounded-md border border-white/10 bg-black/40 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 transition-all duration-200 outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 focus:bg-black/60 hover:border-violet-400/30 hover:bg-black/50 disabled:opacity-50 disabled:cursor-not-allowed font-mono h-16";

interface AnthropicCompatProviderSettingsProps {
  provider: ProviderConfig;
  onUpdate: (updates: Partial<ProviderConfig>) => void;
  onValidate: () => any;
}

export function AnthropicCompatProviderSettings({
  provider,
  onUpdate,
  onValidate
}: AnthropicCompatProviderSettingsProps) {
  const handleFieldChange = (field: string, value: any) => {
    onUpdate({ [field]: value });
  };

  return (
    <BaseProviderSettings provider={provider} onUpdate={onUpdate} onValidate={onValidate}>
      {/* Anthropic Compatible Specific Settings */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Anthropic Compatible Configuration</h5>
        
        {/* API Path */}
        <div>
          <label className="block text-xs text-text-muted mb-1">API Path</label>
          <input
            type="text"
            value={provider.api_path || '/v1/messages'}
            onChange={(e) => handleFieldChange('api_path', e.target.value)}
            placeholder="/v1/messages"
            className={cyberInputClasses}
          />
        </div>

        {/* Models Path */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Models Path</label>
          <input
            type="text"
            value={provider.models_path || '/v1/models'}
            onChange={(e) => handleFieldChange('models_path', e.target.value)}
            placeholder="/v1/models"
            className={cyberInputClasses}
          />
        </div>

        {/* API Version */}
        <div>
          <label className="block text-xs text-text-muted mb-1">API Version</label>
          <input
            type="text"
            value={provider.anthropic_version || '2023-06-01'}
            onChange={(e) => handleFieldChange('anthropic_version', e.target.value)}
            placeholder="2023-06-01"
            className={cyberInputClasses}
          />
        </div>

        {/* Custom Headers */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Custom Headers (JSON)</label>
          <textarea
            value={JSON.stringify(provider.headers || {}, null, 2)}
            onChange={(e) => {
              try {
                const headers = JSON.parse(e.target.value);
                handleFieldChange('headers', headers);
              } catch {
                // Invalid JSON, don't update
              }
            }}
            className={cyberTextareaClasses}
            placeholder='{"anthropic-version": "2023-06-01"}'
          />
        </div>
      </div>

      {/* Model Information */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Claude Models</h5>
        <div className="bg-black/30 rounded-lg p-3 border border-white/10">
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-text-muted">claude-3-5-sonnet</span>
              <span className="text-text-main">• 200K context</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">claude-3-5-haiku</span>
              <span className="text-text-main">• 200K context</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">claude-3-opus</span>
              <span className="text-text-main">• 200K context</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">claude-3-sonnet</span>
              <span className="text-text-main">• 200K context</span>
            </div>
          </div>
        </div>
      </div>

      {/* Advanced Settings */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Advanced Settings</h5>
        
        {/* Max Tokens */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Max Tokens</label>
          <input
            type="number"
            value={provider.max_tokens || 256}
            onChange={(e) => handleFieldChange('max_tokens', parseInt(e.target.value) || 256)}
            min="1"
            max="4096"
            className={cyberInputClasses}
          />
        </div>

        {/* Temperature */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Temperature</label>
          <input
            type="number"
            value={provider.temperature || 0.2}
            onChange={(e) => handleFieldChange('temperature', parseFloat(e.target.value) || 0.2)}
            min="0"
            max="2"
            step="0.1"
            className={cyberInputClasses}
          />
        </div>

        {/* Retries */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Retries</label>
          <input
            type="number"
            value={provider.retries || 0}
            onChange={(e) => handleFieldChange('retries', parseInt(e.target.value) || 0)}
            min="0"
            max="10"
            className={cyberInputClasses}
          />
        </div>
      </div>
    </BaseProviderSettings>
  );
}
