import React, { useState, useEffect } from 'react';
import { Eye, EyeOff, AlertTriangle, CheckCircle2, Info } from 'lucide-react';
import { 
  type ProviderConfig,
  type ValidationResult,
  isCLIProviderType,
  requiresApiKeyForType,
  usesBaseUrlForType
} from '../types';

interface BaseProviderSettingsProps {
  provider: ProviderConfig;
  onUpdate: (updates: Partial<ProviderConfig>) => void;
  onValidate: () => ValidationResult;
  children?: React.ReactNode;
}

export function BaseProviderSettings({ 
  provider, 
  onUpdate, 
  onValidate, 
  children 
}: BaseProviderSettingsProps) {
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [showApiKey, setShowApiKey] = useState(false);

  useEffect(() => {
    const result = onValidate();
    setValidationResult(result);
  }, [provider, onValidate]);

  const handleFieldChange = (field: string, value: any) => {
    onUpdate({ [field]: value });
  };

  const renderValidationStatus = () => {
    if (!validationResult) return null;

    if (validationResult.valid) {
      return (
        <div className="flex items-center gap-2 text-emerald-400 text-xs">
          <CheckCircle2 className="size-3" />
          <span>Configuration valid</span>
        </div>
      );
    }

    return (
      <div className="space-y-1">
        {validationResult.errors.map((error, index) => (
          <div key={index} className="flex items-center gap-2 text-red-400 text-xs">
            <AlertTriangle className="size-3" />
            <span>{error}</span>
          </div>
        ))}
        {validationResult.warnings.map((warning, index) => (
          <div key={index} className="flex items-center gap-2 text-yellow-400 text-xs">
            <Info className="size-3" />
            <span>{warning}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* Basic Settings */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Basic Configuration</h5>
        
        {/* Provider Name */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Provider Name</label>
          <input
            type="text"
            value={provider.name || ''}
            onChange={(e) => handleFieldChange('name', e.target.value)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
            placeholder="My LLM Provider"
          />
        </div>

        {/* API Key - Only show if provider requires it */}
        {provider.type && requiresApiKeyForType(provider.type) && (
          <div>
            <label className="block text-xs text-text-muted mb-1">API Key</label>
            <div className="flex items-center gap-2">
              <input
                type={showApiKey ? "text" : "password"}
                value={provider.api_key || ''}
                onChange={(e) => handleFieldChange('api_key', e.target.value)}
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
            <p className="text-[9px] text-text-dim mt-1">
              API key will be stored securely and used for authentication
            </p>
          </div>
        )}

        {/* Base URL - For API providers */}
        {provider.type && usesBaseUrlForType(provider.type) && (
          <div>
            <label className="block text-xs text-text-muted mb-1">Base URL</label>
            <input
              type="text"
              value={provider.base_url || ''}
              onChange={(e) => handleFieldChange('base_url', e.target.value)}
              className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
              placeholder="https://api.example.com/v1"
            />
          </div>
        )}

        {/* Command - For CLI providers */}
        {provider.type && isCLIProviderType(provider.type) && (
          <div>
            <label className="block text-xs text-text-muted mb-1">Command</label>
            <input
              type="text"
              value={provider.command || ''}
              onChange={(e) => handleFieldChange('command', e.target.value)}
              className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
              placeholder="codex, gemini, etc."
            />
          </div>
        )}

        {/* Timeout */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Timeout (seconds)</label>
          <input
            type="number"
            value={provider.timeout || 60}
            onChange={(e) => handleFieldChange('timeout', parseInt(e.target.value) || 60)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
            min="1"
            max="300"
          />
        </div>
      </div>

      {/* Provider-specific settings */}
      {children}

      {/* Validation Status */}
      <div className="pt-3 border-t border-white/10">
        {renderValidationStatus()}
      </div>
    </div>
  );
}
