import React from 'react';
import { BaseProviderSettings } from './BaseProviderSettings';
import { type ProviderConfig } from '../types';

const cyberInputClasses = "flex h-9 w-full min-w-0 rounded-md border border-white/10 bg-black/40 px-3 py-1 text-sm text-slate-100 placeholder:text-slate-500 transition-all duration-200 outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 focus:bg-black/60 hover:border-violet-400/30 hover:bg-black/50 disabled:opacity-50 disabled:cursor-not-allowed";

const cyberTextareaClasses = "flex w-full min-w-0 rounded-md border border-white/10 bg-black/40 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 transition-all duration-200 outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 focus:bg-black/60 hover:border-violet-400/30 hover:bg-black/50 disabled:opacity-50 disabled:cursor-not-allowed min-h-[80px] resize-y";

interface OpenAICompatProviderSettingsProps {
  provider: ProviderConfig;
  onUpdate: (updates: Partial<ProviderConfig>) => void;
  onValidate: () => any;
}

export function OpenAICompatProviderSettings({
  provider,
  onUpdate,
  onValidate
}: OpenAICompatProviderSettingsProps) {
  const handleFieldChange = (field: string, value: any) => {
    onUpdate({ [field]: value });
  };

  return (
    <BaseProviderSettings provider={provider} onUpdate={onUpdate} onValidate={onValidate}>
      {/* OpenAI Compatible Specific Settings */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">OpenAI Compatible Configuration</h5>
        
        {/* API Path */}
        <div>
          <label className="block text-xs text-text-muted mb-1">API Path</label>
          <input
            type="text"
            value={provider.api_path || '/v1/chat/completions'}
            onChange={(e) => handleFieldChange('api_path', e.target.value)}
            className={`${cyberInputClasses} font-mono`}
            placeholder="/v1/chat/completions"
          />
        </div>

        {/* Models Path */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Models Path</label>
          <input
            type="text"
            value={provider.models_path || '/v1/models'}
            onChange={(e) => handleFieldChange('models_path', e.target.value)}
            className={`${cyberInputClasses} font-mono`}
            placeholder="/v1/models"
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
            className={`${cyberTextareaClasses} font-mono h-16`}
            placeholder='{"Custom-Header": "value"}'
          />
          <p className="text-[9px] text-text-dim mt-1">
            Custom headers in JSON format
          </p>
        </div>
      </div>

      {/* Model Information */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">OpenAI Compatible Models</h5>
        <div className="bg-black/30 rounded-lg p-3 border border-white/10">
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-text-muted">gpt-4</span>
              <span className="text-text-main">• 8K context</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">gpt-4-turbo</span>
              <span className="text-text-main">• 128K context</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">gpt-3.5-turbo</span>
              <span className="text-text-main">• 4K context</span>
            </div>
          </div>
        </div>
      </div>

      {/* Advanced Settings */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Advanced Settings</h5>
        
        {/* Temperature */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Temperature</label>
          <input
            type="number"
            value={provider.temperature || 0.2}
            onChange={(e) => handleFieldChange('temperature', parseFloat(e.target.value) || 0.2)}
            className={cyberInputClasses}
            min="0"
            max="2"
            step="0.1"
          />
        </div>

        {/* Retries */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Retries</label>
          <input
            type="number"
            value={provider.retries || 0}
            onChange={(e) => handleFieldChange('retries', parseInt(e.target.value) || 0)}
            className={cyberInputClasses}
            min="0"
            max="10"
          />
        </div>
      </div>
    </BaseProviderSettings>
  );
}
