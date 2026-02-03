import React from 'react';
import { BaseProviderSettings } from './BaseProviderSettings';
import { type ProviderConfig } from '../types';

interface MaxminiProviderSettingsProps {
  provider: ProviderConfig;
  onUpdate: (updates: Partial<ProviderConfig>) => void;
  onValidate: () => any;
}

export function MaxminiProviderSettings({
  provider,
  onUpdate,
  onValidate
}: MaxminiProviderSettingsProps) {
  const handleFieldChange = (field: string, value: any) => {
    onUpdate({ [field]: value });
  };

  return (
    <BaseProviderSettings provider={provider} onUpdate={onUpdate} onValidate={onValidate}>
      {/* MiniMax Specific Settings */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">MiniMax Configuration</h5>
        
        {/* API Path */}
        <div>
          <label className="block text-xs text-text-muted mb-1">API Path</label>
          <input
            type="text"
            value={provider.api_path || '/text/chatcompletion_pro'}
            onChange={(e) => handleFieldChange('api_path', e.target.value)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
            placeholder="/text/chatcompletion_pro"
          />
        </div>

      </div>

      {/* Model Information */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">MiniMax Models</h5>
        <div className="bg-black/30 rounded-lg p-3 border border-white/10">
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-text-muted">abab6.5</span>
              <span className="text-text-main">• 245K context</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">abab6.5s</span>
              <span className="text-text-main">• 245K context</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">abab6</span>
              <span className="text-text-main">• 8K context</span>
            </div>
          </div>
        </div>
      </div>

      {/* Advanced Settings */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Advanced Settings</h5>
        
        {/* API Path */}
        <div>
          <label className="block text-xs text-text-muted mb-1">API Path</label>
          <input
            type="text"
            value={provider.api_path || ''}
            onChange={(e) => handleFieldChange('api_path', e.target.value)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
            placeholder="/v1/text/chatcompletion_pro"
          />
          <p className="text-[9px] text-text-dim mt-1">
            API endpoint path for MiniMax
          </p>
        </div>

        {/* Temperature */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Temperature</label>
          <input
            type="number"
            value={provider.temperature || 0.7}
            onChange={(e) => handleFieldChange('temperature', parseFloat(e.target.value) || 0.7)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
            min="0"
            max="2"
            step="0.1"
          />
        </div>

        {/* Max Tokens */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Max Tokens</label>
          <input
            type="number"
            value={provider.max_tokens || 2048}
            onChange={(e) => handleFieldChange('max_tokens', parseInt(e.target.value) || 2048)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
            min="1"
            max="245760"
          />
        </div>

        {/* Retries */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Retries</label>
          <input
            type="number"
            value={provider.retries || 3}
            onChange={(e) => handleFieldChange('retries', parseInt(e.target.value) || 3)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
            min="0"
            max="10"
          />
        </div>
      </div>
    </BaseProviderSettings>
  );
}
