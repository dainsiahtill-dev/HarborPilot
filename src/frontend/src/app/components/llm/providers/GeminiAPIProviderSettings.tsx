import React from 'react';
import { BaseProviderSettings } from './BaseProviderSettings';
import { type ProviderConfig, type ProviderValidateFn } from '../types';

const cyberInputClasses = "flex h-9 w-full min-w-0 rounded-md border border-white/10 bg-black/40 px-3 py-1 text-sm text-slate-100 placeholder:text-slate-500 transition-all duration-200 outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 focus:bg-black/60 hover:border-violet-400/30 hover:bg-black/50 disabled:opacity-50 disabled:cursor-not-allowed";

interface GeminiAPIProviderSettingsProps {
  provider: ProviderConfig;
  onUpdate: (updates: Partial<ProviderConfig>) => void;
  onValidate: ProviderValidateFn;
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
            placeholder="/v1beta/models/{model}:generateContent"
            className={cyberInputClasses}
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
            placeholder="/v1beta/models"
            className={cyberInputClasses}
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
            min="0"
            max="2"
            step="0.1"
            className={cyberInputClasses}
          />
        </div>

        {/* Max Tokens */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Max Output Tokens</label>
          <input
            type="number"
            value={provider.max_tokens || 8192}
            onChange={(e) => handleFieldChange('max_tokens', parseInt(e.target.value) || 8192)}
            min="1"
            max="2097152"
            className={cyberInputClasses}
          />
        </div>

        {/* Retries */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Retries</label>
          <input
            type="number"
            value={provider.retries || 3}
            onChange={(e) => handleFieldChange('retries', parseInt(e.target.value) || 3)}
            min="0"
            max="10"
            className={cyberInputClasses}
          />
        </div>
      </div>
    </BaseProviderSettings>
  );
}
