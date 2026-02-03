import React from 'react';
import { BaseProviderSettings } from './BaseProviderSettings';
import { type ProviderConfig } from '../types';

interface OllamaProviderSettingsProps {
  provider: ProviderConfig;
  onUpdate: (updates: Partial<ProviderConfig>) => void;
  onValidate: () => any;
}

export function OllamaProviderSettings({
  provider,
  onUpdate,
  onValidate
}: OllamaProviderSettingsProps) {
  const handleFieldChange = (field: string, value: any) => {
    onUpdate({ [field]: value });
  };

  return (
    <BaseProviderSettings provider={provider} onUpdate={onUpdate} onValidate={onValidate}>
      {/* Ollama Specific Settings */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Ollama Configuration</h5>
        
        {/* Base URL */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Ollama Server URL</label>
          <input
            type="text"
            value={provider.base_url || 'http://127.0.0.1:11434'}
            onChange={(e) => handleFieldChange('base_url', e.target.value)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
            placeholder="http://127.0.0.1:11434"
          />
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
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
          >
            <option value="/api/chat">Chat API</option>
            <option value="/api/generate">Generate API</option>
          </select>
          <p className="text-[9px] text-text-dim mt-1">
            Choose between chat or generate API endpoint
          </p>
        </div>

        {/* Model Information */}
        <div className="bg-black/30 rounded-lg p-3 border border-white/10">
          <h5 className="text-xs font-semibold text-text-main mb-2">Local Model Information</h5>
          <div className="space-y-2 text-xs text-text-dim">
            <p>• Ollama runs models locally on your machine</p>
            <p>• No API keys required for local models</p>
            <p>• Models need to be pulled first: <code className="bg-black/50 px-1 rounded">ollama pull llama3</code></p>
          </div>
        </div>

        {/* Hardware Optimization */}
        <div className="space-y-2">
          <h5 className="text-xs font-semibold text-text-main">Hardware Optimization</h5>
          <div>
            <label className="block text-xs text-text-muted mb-1">GPU Layers (if supported)</label>
            <input
              type="number"
              value={provider.gpu_layers || 0}
              onChange={(e) => handleFieldChange('gpu_layers', parseInt(e.target.value) || 0)}
              className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
              min="0"
              max="100"
              placeholder="Number of GPU layers to offload"
            />
            <p className="text-[9px] text-text-dim mt-1">
              Number of layers to offload to GPU (0 = CPU only)
            </p>
          </div>

          <div>
            <label className="block text-xs text-text-muted mb-1">Context Size</label>
            <input
              type="number"
              value={provider.context_size || 2048}
              onChange={(e) => handleFieldChange('context_size', parseInt(e.target.value) || 2048)}
              className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
              min="512"
              max="32768"
              step="512"
            />
            <p className="text-[9px] text-text-dim mt-1">
              Context window size in tokens
            </p>
          </div>
        </div>

        {/* Common Models Reference */}
        <div className="space-y-2">
          <h5 className="text-xs font-semibold text-text-main">Common Models</h5>
          <div className="bg-black/30 rounded-lg p-3 border border-white/10">
            <div className="space-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-text-muted">llama3:8b</span>
                <span className="text-text-main">• Fast, general purpose</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">llama3:70b</span>
                <span className="text-text-main">• More capable</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">codellama:7b</span>
                <span className="text-text-main">• Code specialized</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">mistral:7b</span>
                <span className="text-text-main">• Efficient</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">mixtral:8x7b</span>
                <span className="text-text-main">• High performance</span>
              </div>
            </div>
          </div>
          <p className="text-[9px] text-text-dim">
            Pull models with: <code className="bg-black/50 px-1 rounded">ollama pull {'{model_name}'}</code>
          </p>
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
            value={provider.temperature || 0.7}
            onChange={(e) => handleFieldChange('temperature', parseFloat(e.target.value) || 0.7)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
            min="0"
            max="2"
            step="0.1"
          />
          <p className="text-[9px] text-text-dim mt-1">
            Controls randomness (0 = deterministic, 2 = very creative)
          </p>
        </div>

        {/* Top K */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Top K</label>
          <input
            type="number"
            value={provider.top_k || 40}
            onChange={(e) => handleFieldChange('top_k', parseInt(e.target.value) || 40)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
            min="1"
            max="100"
          />
          <p className="text-[9px] text-text-dim mt-1">
            Limits vocabulary to top K tokens
          </p>
        </div>

        {/* Top P */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Top P</label>
          <input
            type="number"
            value={provider.top_p || 0.9}
            onChange={(e) => handleFieldChange('top_p', parseFloat(e.target.value) || 0.9)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
            min="0"
            max="1"
            step="0.1"
          />
          <p className="text-[9px] text-text-dim mt-1">
            Nucleus sampling parameter
          </p>
        </div>

        {/* Repeat Penalty */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Repeat Penalty</label>
          <input
            type="number"
            value={provider.repeat_penalty || 1.1}
            onChange={(e) => handleFieldChange('repeat_penalty', parseFloat(e.target.value) || 1.1)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
            min="0"
            max="2"
            step="0.1"
          />
          <p className="text-[9px] text-text-dim mt-1">
            Penalizes repetition (1.0 = no penalty)
          </p>
        </div>
      </div>
    </BaseProviderSettings>
  );
}
