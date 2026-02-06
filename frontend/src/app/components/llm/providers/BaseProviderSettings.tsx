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
  hideApiKey?: boolean;
  hideBaseUrl?: boolean;
}

// Cyberpunk style input classes
const cyberInputClasses = "flex h-9 w-full min-w-0 rounded-md border border-white/10 bg-black/40 px-3 py-1 text-sm text-slate-100 placeholder:text-slate-500 transition-all duration-200 outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 focus:bg-black/60 hover:border-violet-400/30 hover:bg-black/50 disabled:opacity-50 disabled:cursor-not-allowed";

export function BaseProviderSettings({ 
  provider, 
  onUpdate, 
  onValidate, 
  children,
  hideApiKey,
  hideBaseUrl
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
            className={cyberInputClasses}
            placeholder="My LLM Provider"
          />
        </div>

        {/* API Key - Only show if provider requires it and not hidden */}
        {provider.type && requiresApiKeyForType(provider.type) && !hideApiKey && (
          <div>
            <label className="block text-xs text-text-muted mb-1">API Key</label>
            <div className="flex items-center gap-2">
              <input
                type={showApiKey ? "text" : "password"}
                value={provider.api_key || ''}
                onChange={(e) => handleFieldChange('api_key', e.target.value)}
                className={`${cyberInputClasses} flex-1 font-mono`}
                placeholder="Enter your API key"
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="p-2 rounded border border-white/10 hover:border-accent/40 bg-black/40 text-slate-300 hover:text-slate-100 transition-colors"
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
        {provider.type && usesBaseUrlForType(provider.type) && !hideBaseUrl && (
          <div>
            <label className="block text-xs text-text-muted mb-1">Base URL</label>
            <input
              type="text"
              value={provider.base_url || ''}
              onChange={(e) => handleFieldChange('base_url', e.target.value)}
              className={`${cyberInputClasses} font-mono`}
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
              className={`${cyberInputClasses} font-mono`}
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
            className={cyberInputClasses}
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
