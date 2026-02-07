import React, { useState, useEffect } from 'react';
import { BaseProviderSettings } from './BaseProviderSettings';
import { type ProviderConfig, type ProviderValidateFn } from '../types';
import { Loader2, RefreshCw, Check, AlertCircle } from 'lucide-react';

interface OllamaProviderSettingsProps {
  provider: ProviderConfig;
  onUpdate: (updates: Partial<ProviderConfig>) => void;
  onValidate: ProviderValidateFn;
}

const cyberInputClasses = "flex h-9 w-full min-w-0 rounded-md border border-white/10 bg-black/40 px-3 py-1 text-sm text-slate-100 placeholder:text-slate-500 transition-all duration-200 outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 focus:bg-black/60 hover:border-violet-400/30 hover:bg-black/50 disabled:opacity-50 disabled:cursor-not-allowed";
const cyberSelectClasses = "flex h-9 w-full min-w-0 rounded-md border border-white/10 bg-black/40 px-3 py-1 text-sm text-slate-100 transition-all duration-200 outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 focus:bg-black/60 hover:border-violet-400/30 hover:bg-black/50 cursor-pointer appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2224%22%20height%3D%2224%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%2394a3b8%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpolyline%20points%3D%226%209%2012%2015%2018%209%22%3E%3C%2Fpolyline%3E%3C%2Fsvg%3E')] bg-[length:16px] bg-[right_8px_center] bg-no-repeat pr-10";

export function OllamaProviderSettings({
  provider,
  onUpdate,
  onValidate
}: OllamaProviderSettingsProps) {
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [modelError, setModelError] = useState<string | null>(null);
  const [isCustomModel, setIsCustomModel] = useState(false);

  const handleFieldChange = (field: string, value: any) => {
    onUpdate({ [field]: value });
  };

  const fetchModels = async () => {
    setIsLoadingModels(true);
    setModelError(null);
    const baseUrl = provider.base_url || 'http://127.0.0.1:11434';
    
    try {
      // Clean up base URL to ensure valid fetch
      const url = new URL('/api/tags', baseUrl).toString();
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error(`Failed to connect: ${response.statusText}`);
      }
      
      const data = await response.json();
      const models = (data.models || []).map((m: any) => m.name);
      setAvailableModels(models);
      
      // If current model is not in list and not empty, set as custom
      if (provider.model && !models.includes(provider.model)) {
        setIsCustomModel(true);
      }
    } catch (error) {
      console.error('Failed to fetch Ollama models:', error);
      setModelError(error instanceof Error ? error.message : 'Failed to fetch models');
    } finally {
      setIsLoadingModels(false);
    }
  };

  // Initial fetch if URL is present
  useEffect(() => {
    if (provider.base_url) {
      fetchModels();
    }
  }, []); // Only modify this if we want auto-refetch on URL change, but manual is safer for edits

  const handleModelSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    if (value === 'custom') {
      setIsCustomModel(true);
      // Don't clear model immediately to allow "editing" current if valid, 
      // or clear if starting fresh. For now keep current.
    } else {
      setIsCustomModel(false);
      handleFieldChange('model', value);
    }
  };

  return (
    <BaseProviderSettings provider={provider} onUpdate={onUpdate} onValidate={onValidate}>
      {/* Ollama Specific Settings */}
      <div className="space-y-4">
        <h5 className="text-xs font-semibold text-text-main">Ollama Configuration</h5>
        
        {/* Base URL */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Ollama Server URL</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={provider.base_url || 'http://127.0.0.1:11434'}
              onChange={(e) => handleFieldChange('base_url', e.target.value)}
              className={`${cyberInputClasses} flex-1 font-mono`}
              placeholder="http://127.0.0.1:11434"
            />
          </div>
          <p className="text-[9px] text-text-dim mt-1">
            URL of your local Ollama server (default: http://127.0.0.1:11434)
          </p>
        </div>

        {/* API Path */}
        <div>
          <label className="block text-xs text-text-muted mb-1">API Path</label>
          <select
            value={provider.api_path || '/api/chat'}
            onChange={(e) => handleFieldChange('api_path', e.target.value)}
            className={cyberSelectClasses}
          >
            <option value="/api/chat">Chat API (/api/chat)</option>
            <option value="/api/generate">Generate API (/api/generate)</option>
            <option value="/v1/chat/completions">OpenAI Compatible (/v1/chat/completions)</option>
          </select>
        </div>

        {/* Model Selection */}
        <div className="bg-black/20 rounded-lg p-3 border border-white/5">
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-semibold text-text-main">Model Selection</label>
            <button
              type="button"
              onClick={fetchModels}
              disabled={isLoadingModels}
              className="text-[10px] flex items-center gap-1 text-cyan-400 hover:text-cyan-300 disabled:opacity-50"
            >
              <RefreshCw className={`size-3 ${isLoadingModels ? 'animate-spin' : ''}`} />
              {isLoadingModels ? 'Scanning...' : 'Refresh Models'}
            </button>
          </div>

          <div className="space-y-2">
            <select
              value={isCustomModel ? 'custom' : (provider.model || '')}
              onChange={handleModelSelect}
              className={cyberSelectClasses}
            >
              <option value="" disabled>Select a model...</option>
              {availableModels.map(model => (
                <option key={model} value={model}>{model}</option>
              ))}
              <option value="custom">Custom / Manual Input...</option>
            </select>

            {isCustomModel && (
              <div className="animate-in fade-in slide-in-from-top-1">
                <input
                  type="text"
                  value={provider.model || ''}
                  onChange={(e) => handleFieldChange('model', e.target.value)}
                  className="flex h-9 w-full min-w-0 rounded-md border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-sm text-slate-100 placeholder:text-slate-500 transition-all duration-200 outline-none focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 focus:bg-black/60 font-mono"
                  placeholder="Enter model name (e.g., llama3:8b)"
                  autoFocus
                />
                <p className="text-[9px] text-indigo-300 mt-1 flex items-center gap-1">
                  <AlertCircle className="size-3" />
                  Manual entry enabled. Ensure this model is pulled in Ollama.
                </p>
              </div>
            )}
            
            {modelError && (
              <div className="text-[10px] text-rose-300 bg-rose-500/10 px-2 py-1.5 rounded border border-rose-500/20 flex items-start gap-1.5">
                 <AlertCircle className="size-3 shrink-0 mt-0.5" />
                 <div>
                   <p className="font-semibold">Connection Failed</p>
                   <p className="opacity-80">{modelError}</p>
                 </div>
              </div>
            )}
            
            {!modelError && availableModels.length > 0 && (
              <div className="text-[9px] text-emerald-400/80 flex items-center gap-1 px-1">
                <Check className="size-3" />
                Found {availableModels.length} local models
              </div>
            )}
          </div>
        </div>

        {/* Hardware Optimization */}
        <div className="space-y-2 pt-2 border-t border-white/5">
          <h5 className="text-xs font-semibold text-text-main">Performance</h5>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-text-muted mb-1">GPU Layers</label>
              <input
                type="number"
                value={provider.gpu_layers || 0}
                onChange={(e) => handleFieldChange('gpu_layers', parseInt(e.target.value) || 0)}
                placeholder="0"
                className={cyberInputClasses}
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">Context Size</label>
              <input
                type="number"
                value={provider.context_size || 2048}
                onChange={(e) => handleFieldChange('context_size', parseInt(e.target.value) || 2048)}
                step="512"
                className={cyberInputClasses}
              />
            </div>
          </div>
        </div>

        {/* Advanced Settings */}
        <div className="space-y-3 pt-2 border-t border-white/5">
          <h5 className="text-xs font-semibold text-text-main">Generation Parameters</h5>
          <div className="grid grid-cols-2 gap-3">
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
            {/* Top P */}
            <div>
              <label className="block text-xs text-text-muted mb-1">Top P</label>
              <input
                type="number"
                value={provider.top_p || 0.9}
                onChange={(e) => handleFieldChange('top_p', parseFloat(e.target.value) || 0.9)}
                min="0"
                max="1"
                step="0.1"
                className={cyberInputClasses}
              />
            </div>
          </div>
        </div>
      </div>
    </BaseProviderSettings>
  );
}
