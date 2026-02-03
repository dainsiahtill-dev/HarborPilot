import React from 'react';
import { BaseProviderSettings } from './BaseProviderSettings';
import { type ProviderConfig } from '../types';

interface GeminiAPIProviderSettingsProps {
  provider: ProviderConfig;
  onUpdate: (updates: Partial<ProviderConfig>) => void;
  onValidate: () => any;
}

export function GeminiAPIProviderSettings({
  provider,
  onUpdate,
  onValidate
}: GeminiAPIProviderSettingsProps) {
  const handleFieldChange = (field: string, value: any) => {
    onUpdate({ [field]: value });
  };

  return (
    <BaseProviderSettings provider={provider} onUpdate={onUpdate} onValidate={onValidate}>
      {/* Gemini API Specific Settings */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Gemini API Configuration</h5>
        
        {/* API Path */}
        <div>
          <label className="block text-xs text-text-muted mb-1">API Path</label>
          <input
            type="text"
            value={provider.api_path || '/v1beta/models/{model}:generateContent'}
            onChange={(e) => handleFieldChange('api_path', e.target.value)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
            placeholder="/v1beta/models/{model}:generateContent"
          />
          <p className="text-[9px] text-text-dim mt-1">
            Use {'{model}'} placeholder for dynamic model selection
          </p>
        </div>

        {/* Models Path */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Models List Path</label>
          <input
            type="text"
            value={provider.models_path || '/v1beta/models'}
            onChange={(e) => handleFieldChange('models_path', e.target.value)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
            placeholder="/v1beta/models"
          />
        </div>
      </div>

      {/* Model Information */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Gemini Models</h5>
        <div className="bg-black/30 rounded-lg p-3 border border-white/10">
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-text-muted">gemini-1.5-pro</span>
              <span className="text-text-main">• 2M context</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">gemini-1.5-flash</span>
              <span className="text-text-main">• 1M context</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">gemini-1.0-pro</span>
              <span className="text-text-main">• 32K context</span>
            </div>
          </div>
        </div>
        <p className="text-[9px] text-text-dim">
          Get API key from <a href="https://aistudio.google.com/app/apikey" target="_blank" className="text-accent hover:underline">Google AI Studio</a>
        </p>
      </div>

      {/* Advanced Settings */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Advanced Settings</h5>
        
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
          <label className="block text-xs text-text-muted mb-1">Max Output Tokens</label>
          <input
            type="number"
            value={provider.max_tokens || 8192}
            onChange={(e) => handleFieldChange('max_tokens', parseInt(e.target.value) || 8192)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
            min="1"
            max="2097152"
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
