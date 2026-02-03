import React from 'react';
import { BaseProviderSettings } from './BaseProviderSettings';
import { CLI_MODES, type CLIMode, type ProviderConfig } from '../types';

interface GeminiCLIProviderSettingsProps {
  provider: ProviderConfig;
  onUpdate: (updates: Partial<ProviderConfig>) => void;
  onValidate: () => any;
}

export function GeminiCLIProviderSettings({
  provider,
  onUpdate,
  onValidate
}: GeminiCLIProviderSettingsProps) {
  const handleFieldChange = (field: string, value: any) => {
    onUpdate({ [field]: value });
  };

  const env = provider.env || {};
  const cliMode: CLIMode =
    provider.cli_mode === CLI_MODES.TUI || provider.cli_mode === CLI_MODES.HEADLESS
      ? provider.cli_mode
      : CLI_MODES.HEADLESS;
  const headlessArgs = Array.isArray(provider.args) && provider.args.length
    ? provider.args
    : ['chat', '--model', '{model}', '--prompt', '{prompt}'];
  const headlessTemplate = [provider.command || 'gemini', ...headlessArgs].join(' ');
  const missingModelPlaceholder = !headlessTemplate.includes('{model}');
  const missingPromptPlaceholder = !headlessTemplate.includes('{prompt}');

  return (
    <BaseProviderSettings provider={provider} onUpdate={onUpdate} onValidate={onValidate}>
      {/* Gemini CLI Specific Settings */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Gemini CLI Configuration</h5>

        {/* CLI Mode */}
        <div>
          <label className="block text-xs text-text-muted mb-1">CLI Mode</label>
          <select
            value={cliMode}
            onChange={(e) => handleFieldChange('cli_mode', e.target.value)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
          >
            <option value={CLI_MODES.HEADLESS}>Headless (non-interactive)</option>
            <option value={CLI_MODES.TUI}>TUI (interactive)</option>
          </select>
          <p className="text-[9px] text-text-dim mt-1">
            Headless mode is recommended for automation and testing.
          </p>
        </div>
        
        {/* Google API Key */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Google API Key</label>
          <input
            type="password"
            value={env.GOOGLE_API_KEY || ''}
            onChange={(e) => handleFieldChange('env', { ...env, GOOGLE_API_KEY: e.target.value })}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
            placeholder="Enter your Google API key"
          />
          <p className="text-[9px] text-text-dim mt-1">
            Get your API key from <a href="https://aistudio.google.com/app/apikey" target="_blank" className="text-accent hover:underline">Google AI Studio</a>
          </p>
        </div>

        {/* API Key Source */}
        <div>
          <label className="block text-xs text-text-muted mb-1">API Key Source</label>
          <select
            value={env.GOOGLE_GENAI_USE_VERTEXAI || 'false'}
            onChange={(e) => handleFieldChange('env', { ...env, GOOGLE_GENAI_USE_VERTEXAI: e.target.value })}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
          >
            <option value="false">Google AI Studio</option>
            <option value="true">Vertex AI</option>
          </select>
          <p className="text-[9px] text-text-dim mt-1">
            Choose between Google AI Studio or Vertex AI as the API source
          </p>
        </div>

        {cliMode === CLI_MODES.HEADLESS && (
          <>
            {/* Command Arguments */}
            <div>
              <label className="block text-xs text-text-muted mb-1">Command Arguments (one per line)</label>
              <textarea
                value={(provider.args || []).join('\n')}
                onChange={(e) => handleFieldChange('args', e.target.value.split('\n').filter(arg => arg.trim()))}
                className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono h-16"
                placeholder="chat --model {'{model}'} --prompt {'{prompt}'}"
              />
              <p className="text-[9px] text-text-dim mt-1">
                Gemini CLI arguments. Use {'{model}'} and {'{prompt}'} placeholders.
              </p>
            </div>

            {/* Headless Template */}
            <div className="bg-black/20 rounded p-3 space-y-2">
              <h6 className="text-xs font-semibold text-text-main">Headless Mode Template</h6>
              <div className="text-[10px] text-text-dim">
                Ensure <code className="bg-black/40 px-1 rounded">{'{model}'}</code> and{' '}
                <code className="bg-black/40 px-1 rounded">{'{prompt}'}</code> placeholders are present.
              </div>
              <div className="text-[10px] font-mono text-text-main bg-black/30 rounded px-2 py-1 border border-white/10">
                {headlessTemplate}
              </div>
              {(missingModelPlaceholder || missingPromptPlaceholder) && (
                <div className="text-[10px] text-yellow-300">
                  Missing placeholders: {missingModelPlaceholder ? '{model}' : ''}
                  {missingModelPlaceholder && missingPromptPlaceholder ? ', ' : ''}
                  {missingPromptPlaceholder ? '{prompt}' : ''}
                </div>
              )}
            </div>
          </>
        )}

        {cliMode === CLI_MODES.TUI && (
          <div className="bg-black/20 rounded p-3 space-y-2">
            <h6 className="text-xs font-semibold text-text-main">TUI Mode Instructions</h6>
            <div className="text-[10px] text-text-dim space-y-1">
              <p><span className="text-text-muted">Model Discovery:</span> Run <code className="bg-black/40 px-1 rounded">gemini models list</code></p>
              <p><span className="text-text-muted">Interactive Session:</span> Run <code className="bg-black/40 px-1 rounded">gemini chat</code></p>
            </div>
          </div>
        )}

        {/* Health Check Arguments */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Health Check Arguments</label>
          <input
            type="text"
            value={provider.health_args || 'version'}
            onChange={(e) => handleFieldChange('health_args', e.target.value.split(' ').filter(arg => arg.trim()))}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
            placeholder="version"
          />
          <p className="text-[9px] text-text-dim mt-1">
            Arguments to check if Gemini CLI is working
          </p>
        </div>

        {/* Model Listing Arguments */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Model Listing Arguments</label>
          <input
            type="text"
            value={provider.list_args || 'models list'}
            onChange={(e) => handleFieldChange('list_args', e.target.value.split(' ').filter(arg => arg.trim()))}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
            placeholder="models list"
          />
          <p className="text-[9px] text-text-dim mt-1">
            Arguments to list available models
          </p>
        </div>
      </div>

      {/* Gemini Model Information */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Gemini Models</h5>
        <div className="bg-black/30 rounded-lg p-3 border border-white/10">
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-text-muted">gemini-1.5-pro</span>
              <span className="text-text-main">• Advanced, 2M context</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">gemini-1.5-flash</span>
              <span className="text-text-main">• Fast, 1M context</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">gemini-1.0-pro</span>
              <span className="text-text-main">• Legacy model</span>
            </div>
          </div>
        </div>
        <p className="text-[9px] text-text-dim">
          Install Gemini CLI: <code className="bg-black/50 px-1 rounded">pip install google-generativeai</code>
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
          <p className="text-[9px] text-text-dim mt-1">
            Controls randomness (0 = deterministic, 2 = very creative)
          </p>
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
            max="8192"
          />
          <p className="text-[9px] text-text-dim mt-1">
            Maximum number of tokens in the response
          </p>
        </div>

        {/* Streaming */}
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-xs text-text-muted">
            <input
              type="checkbox"
              checked={provider.streaming === true}
              onChange={(e) => handleFieldChange('streaming', e.target.checked)}
              className="rounded border-white/20 bg-black/30"
            />
            <span>Enable Streaming</span>
          </label>
          <p className="text-[9px] text-text-dim ml-5">
            Stream responses as they are generated (if supported)
          </p>
        </div>
      </div>

      {/* Environment Variables */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Environment Variables</h5>
        <div>
          <label className="block text-xs text-text-muted mb-1">Additional Environment Variables (JSON)</label>
          <textarea
            value={JSON.stringify(env, null, 2)}
            onChange={(e) => {
              try {
                const newEnv = JSON.parse(e.target.value);
                handleFieldChange('env', newEnv);
              } catch {
                // Invalid JSON, don't update
              }
            }}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono h-20"
            placeholder='{"GOOGLE_GENAI_API_KEY": "your-key", "OTHER_VAR": "value"}'
          />
          <p className="text-[9px] text-text-dim mt-1">
            Additional environment variables in JSON format
          </p>
        </div>
      </div>
    </BaseProviderSettings>
  );
}
