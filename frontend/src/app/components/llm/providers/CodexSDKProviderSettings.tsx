import React from 'react';
import { BaseProviderSettings } from './BaseProviderSettings';
import { type ProviderConfig } from '../types';

interface CodexSDKProviderSettingsProps {
  provider: ProviderConfig;
  onUpdate: (updates: Partial<ProviderConfig>) => void;
  onValidate: () => any;
}

export function CodexSDKProviderSettings({
  provider,
  onUpdate,
  onValidate
}: CodexSDKProviderSettingsProps) {
  const handleFieldChange = (field: string, value: any) => {
    onUpdate({ [field]: value });
  };

  return (
    <BaseProviderSettings provider={provider} onUpdate={onUpdate} onValidate={onValidate}>
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Codex SDK Configuration</h5>

        <div>
          <label className="block text-xs text-text-muted mb-1">Default Model</label>
          <input
            type="text"
            value={provider.default_model || ''}
            onChange={(e) => handleFieldChange('default_model', e.target.value)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
            placeholder="gpt-4-codex"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-text-muted mb-1">Max Retries</label>
            <input
              type="number"
              value={provider.max_retries ?? 3}
              onChange={(e) => handleFieldChange('max_retries', parseInt(e.target.value) || 0)}
              className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
              min="0"
              max="10"
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Temperature</label>
            <input
              type="number"
              value={provider.temperature ?? 0.2}
              onChange={(e) => handleFieldChange('temperature', parseFloat(e.target.value) || 0)}
              className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
              min="0"
              max="2"
              step="0.1"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <label className="flex items-center gap-2 text-xs text-text-muted">
            <input
              type="checkbox"
              checked={provider.thinking_mode ?? true}
              onChange={(e) => handleFieldChange('thinking_mode', e.target.checked)}
              className="rounded border-white/20 bg-black/40"
            />
            Thinking Mode
          </label>
          <label className="flex items-center gap-2 text-xs text-text-muted">
            <input
              type="checkbox"
              checked={provider.streaming ?? false}
              onChange={(e) => handleFieldChange('streaming', e.target.checked)}
              className="rounded border-white/20 bg-black/40"
            />
            Streaming
          </label>
        </div>

        <div>
          <label className="block text-xs text-text-muted mb-1">SDK Params (JSON)</label>
          <textarea
            value={JSON.stringify(provider.sdk_params || {}, null, 2)}
            onChange={(e) => {
              try {
                const params = JSON.parse(e.target.value);
                handleFieldChange('sdk_params', params);
              } catch {
                // ignore invalid JSON
              }
            }}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono h-20"
            placeholder='{"organization": "..."}'
          />
          <p className="text-[9px] text-text-dim mt-1">Extra SDK client params merged into the client constructor.</p>
        </div>
      </div>
    </BaseProviderSettings>
  );
}
