import React from 'react';
import { BaseProviderSettings } from './BaseProviderSettings';
import { CLI_MODES, type CLIMode, type ProviderConfig } from '../types';

interface CodexCLIProviderSettingsProps {
  provider: ProviderConfig;
  onUpdate: (updates: Partial<ProviderConfig>) => void;
  onValidate: () => any;
}

export function CodexCLIProviderSettings({
  provider,
  onUpdate,
  onValidate
}: CodexCLIProviderSettingsProps) {
  const handleFieldChange = (field: string, value: any) => {
    onUpdate({ [field]: value });
  };

  const codexExec = provider.codex_exec || {};
  const cliMode: CLIMode =
    provider.cli_mode === CLI_MODES.TUI || provider.cli_mode === CLI_MODES.HEADLESS
      ? provider.cli_mode
      : CLI_MODES.HEADLESS;

  const buildHeadlessArgs = (): string[] => {
    const opts = typeof codexExec === 'object' && codexExec ? codexExec : {};
    const args: string[] = ['exec'];

    const cd = String((opts as Record<string, unknown>).cd || '').trim();
    if (cd) {
      args.push('--cd', cd);
    }

    const color = String((opts as Record<string, unknown>).color || '').trim();
    if (['always', 'never', 'auto'].includes(color)) {
      args.push('--color', color);
    }

    if ((opts as Record<string, unknown>).skip_git_repo_check !== false) {
      args.push('--skip-git-repo-check');
    }

    const sandbox = String((opts as Record<string, unknown>).sandbox || '').trim();
    if (sandbox) {
      args.push('--sandbox', sandbox);
    }

    args.push('--model', '{model}');

    const jsonMode = (opts as Record<string, unknown>).json;
    if (jsonMode !== false) {
      args.push(jsonMode === 'experimental' ? '--experimental-json' : '--json');
    }

    const approvals = String(
      (opts as Record<string, unknown>).ask_for_approval ||
        (opts as Record<string, unknown>).approvals ||
        ''
    ).trim();
    if (approvals) {
      args.push('--ask-for-approval', approvals);
    }

    if ((opts as Record<string, unknown>).oss) {
      args.push('--oss');
    }

    const addDirs = (opts as Record<string, unknown>).add_dirs;
    if (Array.isArray(addDirs)) {
      addDirs.filter(Boolean).forEach((entry) => {
        args.push('--add-dir', String(entry));
      });
    }

    const images = (opts as Record<string, unknown>).images;
    if (Array.isArray(images)) {
      images.filter(Boolean).forEach((entry) => {
        args.push('--image', String(entry));
      });
    }

    const outputSchema = String((opts as Record<string, unknown>).output_schema || '').trim();
    if (outputSchema) {
      args.push('--output-schema', outputSchema);
    }

    const outputLast = String((opts as Record<string, unknown>).output_last_message || '').trim();
    if (outputLast) {
      args.push('--output-last-message', outputLast);
    }

    const profile = String((opts as Record<string, unknown>).profile || '').trim();
    if (profile) {
      args.push('--profile', profile);
    }

    const configOverrides = (opts as Record<string, unknown>).config;
    if (Array.isArray(configOverrides)) {
      configOverrides.filter(Boolean).forEach((entry) => {
        args.push('--config', String(entry));
      });
    }

    if ((opts as Record<string, unknown>).yolo) {
      args.push('--yolo');
    } else if ((opts as Record<string, unknown>).full_auto) {
      args.push('--full-auto');
    }

    args.push('{prompt}');
    return args;
  };

  const headlessTemplate = [provider.command || 'codex', ...buildHeadlessArgs()].join(' ');
  const missingModelPlaceholder = !headlessTemplate.includes('{model}');
  const missingPromptPlaceholder = !headlessTemplate.includes('{prompt}');

  return (
    <BaseProviderSettings provider={provider} onUpdate={onUpdate} onValidate={onValidate}>
      {/* Codex CLI Specific Settings */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Codex CLI Configuration</h5>

        {/* CLI Mode */}
        <div>
          <label className="block text-xs text-text-muted mb-1">CLI Mode</label>
          <select
            value={cliMode}
            onChange={(e) => handleFieldChange('cli_mode', e.target.value)}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
          >
            <option value={CLI_MODES.HEADLESS}>Headless (exec --json)</option>
            <option value={CLI_MODES.TUI}>TUI (interactive)</option>
          </select>
          <p className="text-[9px] text-text-dim mt-1">
            Headless mode is recommended for automation. TUI mode is best for manual discovery.
          </p>
        </div>
        
        {/* Working Directory */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Working Directory</label>
          <input
            type="text"
            value={codexExec.cd || ''}
            onChange={(e) => handleFieldChange('codex_exec', { ...codexExec, cd: e.target.value })}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
            placeholder="/path/to/working/directory"
          />
          <p className="text-[9px] text-text-dim mt-1">
            Directory where Codex CLI will execute commands
          </p>
        </div>

        {/* Approval Mode */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Approval Mode</label>
          <select
            value={codexExec.ask_for_approval || 'on-request'}
            onChange={(e) => handleFieldChange('codex_exec', { ...codexExec, ask_for_approval: e.target.value })}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
          >
            <option value="untrusted">Untrusted (Always ask)</option>
            <option value="on-failure">On Failure</option>
            <option value="on-request">On Request</option>
            <option value="never">Never</option>
          </select>
          <p className="text-[9px] text-text-dim mt-1">
            Controls when Codex asks for approval before running commands
          </p>
        </div>

        {/* Sandbox Mode */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Sandbox Strategy</label>
          <select
            value={codexExec.sandbox || 'read-only'}
            onChange={(e) => handleFieldChange('codex_exec', { ...codexExec, sandbox: e.target.value })}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
          >
            <option value="read-only">Read Only (Safe Default)</option>
            <option value="workspace-write">Workspace Write</option>
            <option value="danger-full-access">Danger Full Access</option>
          </select>
          <p className="text-[9px] text-text-dim mt-1">
            Controls the scope of generated shell commands. Read-only is safest.
          </p>
        </div>

        {/* JSON Mode */}
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-xs text-text-muted">
            <input
              type="checkbox"
              checked={codexExec.json !== false}
              onChange={(e) => handleFieldChange('codex_exec', { ...codexExec, json: e.target.checked })}
              className="rounded border-white/20 bg-black/30"
            />
            <span>JSON Mode</span>
          </label>
          <p className="text-[9px] text-text-dim ml-5">
            Output JSON events for machine processing (recommended for HarborPilot)
          </p>
        </div>

        {/* Color Output */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Color Output</label>
          <select
            value={codexExec.color || 'never'}
            onChange={(e) => handleFieldChange('codex_exec', { ...codexExec, color: e.target.value })}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
          >
            <option value="never">Never</option>
            <option value="auto">Auto</option>
            <option value="always">Always</option>
          </select>
          <p className="text-[9px] text-text-dim mt-1">
            Control ANSI color output (disabled for JSON mode)
          </p>
        </div>

        {/* Additional Options */}
        <div className="space-y-3">
          <h5 className="text-xs font-semibold text-text-main">Automation Options</h5>
          
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-xs text-text-muted">
              <input
                type="checkbox"
                checked={codexExec.skip_git_repo_check !== false}
                onChange={(e) => handleFieldChange('codex_exec', { ...codexExec, skip_git_repo_check: e.target.checked })}
                className="rounded border-white/20 bg-black/30"
              />
              <span>Skip Git Repo Check</span>
            </label>
            <p className="text-[9px] text-text-dim ml-5">
              Allow running in non-Git repositories (use with caution)
            </p>
          </div>

          <div className="space-y-2">
            <label className="flex items-center gap-2 text-xs text-text-muted">
              <input
                type="checkbox"
                checked={codexExec.full_auto === true}
                onChange={(e) => handleFieldChange('codex_exec', { ...codexExec, full_auto: e.target.checked })}
                className="rounded border-white/20 bg-black/30"
              />
              <span>Full Auto Mode</span>
            </label>
            <p className="text-[9px] text-text-dim ml-5">
              Apply automation preset (workspace-write + on-request approval)
            </p>
          </div>

          <div className="space-y-2">
            <label className="flex items-center gap-2 text-xs text-text-muted">
              <input
                type="checkbox"
                checked={codexExec.yolo === true}
                onChange={(e) => handleFieldChange('codex_exec', { ...codexExec, yolo: e.target.checked })}
                className="rounded border-white/20 bg-black/30"
              />
              <span>YOLO Mode (Dangerous!)</span>
            </label>
            <p className="text-[9px] text-text-dim ml-5 text-red-400">
              ⚠️ Skip all approvals and sandbox checks - only for isolated environments!
            </p>
          </div>

          <div className="space-y-2">
            <label className="flex items-center gap-2 text-xs text-text-muted">
              <input
                type="checkbox"
                checked={codexExec.oss === true}
                onChange={(e) => handleFieldChange('codex_exec', { ...codexExec, oss: e.target.checked })}
                className="rounded border-white/20 bg-black/30"
              />
              <span>OSS Provider</span>
            </label>
            <p className="text-[9px] text-text-dim ml-5">
              Use local OSS provider (requires Ollama running locally)
            </p>
          </div>
        </div>

        {cliMode === CLI_MODES.HEADLESS && (
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
        )}

        {cliMode === CLI_MODES.TUI && (
          <>
            {/* Manual Model Entry (for TUI mode) */}
            <div>
              <label className="block text-xs text-text-muted mb-1">Manual Model Entry</label>
              <textarea
                value={(provider.manual_models || []).join('\n')}
                onChange={(e) =>
                  handleFieldChange(
                    'manual_models',
                    e.target.value.split('\n').filter((model) => model.trim())
                  )
                }
                className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono h-16"
                placeholder="gpt-4-codex&#10;gpt-5.2-codex&#10;custom-model-name"
              />
              <p className="text-[9px] text-text-dim mt-1">
                Enter models manually. Run 'codex' then type '/models' to see available models.
              </p>
            </div>

            {/* TUI Instructions */}
            <div className="bg-black/20 rounded p-3 space-y-2">
              <h6 className="text-xs font-semibold text-text-main">TUI Mode Instructions</h6>
              <div className="text-[10px] text-text-dim space-y-1">
                <p><span className="text-text-muted">Model Discovery:</span> Run 'codex' → type '/models'</p>
                <p><span className="text-text-muted">Session Status:</span> Run 'codex' → type '/status'</p>
                <p><span className="text-text-muted">Permissions:</span> Run 'codex' → type '/permissions'</p>
                <p><span className="text-text-muted">Help:</span> Run 'codex' → type '/help'</p>
              </div>
            </div>
          </>
        )}

        {/* Profile */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Profile</label>
          <input
            type="text"
            value={codexExec.profile || ''}
            onChange={(e) => handleFieldChange('codex_exec', { ...codexExec, profile: e.target.value })}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm"
            placeholder="default, codex, or custom profile name"
          />
          <p className="text-[9px] text-text-dim mt-1">
            Load configuration profile from ~/.codex/config.toml
          </p>
        </div>

        {/* Configuration Overrides */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Configuration Overrides (key=value)</label>
          <textarea
            value={(codexExec.config || []).join('\n')}
            onChange={(e) => handleFieldChange('codex_exec', { 
              ...codexExec, 
              config: e.target.value.split('\n').filter(config => config.trim() && config.includes('='))
            })}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono h-16"
            placeholder="key1=value1&#10;key2=value2"
          />
          <p className="text-[9px] text-text-dim mt-1">
            Inline configuration overrides (one per line, key=value format)
          </p>
        </div>

        {/* Additional Directories */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Additional Directories</label>
          <textarea
            value={(codexExec.add_dirs || []).join('\n')}
            onChange={(e) => handleFieldChange('codex_exec', { 
              ...codexExec, 
              add_dirs: e.target.value.split('\n').filter(dir => dir.trim()) 
            })}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono h-16"
            placeholder="/path/to/dir1&#10;/path/to/dir2"
          />
          <p className="text-[9px] text-text-dim mt-1">
            Grant write access to additional directories outside workspace
          </p>
        </div>

        {/* Images */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Images</label>
          <textarea
            value={(codexExec.images || []).join('\n')}
            onChange={(e) => handleFieldChange('codex_exec', { 
              ...codexExec, 
              images: e.target.value.split('\n').filter(image => image.trim()) 
            })}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono h-16"
            placeholder="/path/to/image1.png&#10;/path/to/image2.jpg"
          />
          <p className="text-[9px] text-text-dim mt-1">
            Attach images to the first message (one per line)
          </p>
        </div>

        {/* Output Schema */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Output Schema</label>
          <input
            type="text"
            value={codexExec.output_schema || ''}
            onChange={(e) => handleFieldChange('codex_exec', { ...codexExec, output_schema: e.target.value })}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
            placeholder="/path/to/schema.json"
          />
          <p className="text-[9px] text-text-dim mt-1">
            JSON Schema file for validating final output (better for pipelines)
          </p>
        </div>

        {/* Output Last Message */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Output Last Message To</label>
          <input
            type="text"
            value={codexExec.output_last_message || ''}
            onChange={(e) => handleFieldChange('codex_exec', { ...codexExec, output_last_message: e.target.value })}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono"
            placeholder=".harborpilot/runtime/CODEX_LAST_MESSAGE.md"
          />
          <p className="text-[9px] text-text-dim mt-1">
            Write last assistant message to file for script continuation
          </p>
        </div>
      </div>

      {/* Environment Variables */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Environment Variables</h5>
        <div>
          <label className="block text-xs text-text-muted mb-1">Environment Variables (JSON)</label>
          <textarea
            value={JSON.stringify(provider.env || {}, null, 2)}
            onChange={(e) => {
              try {
                const env = JSON.parse(e.target.value);
                handleFieldChange('env', env);
              } catch {
                // Invalid JSON, don't update
              }
            }}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono h-20"
            placeholder='{"KEY": "value"}'
          />
          <p className="text-[9px] text-text-dim mt-1">
            Environment variables in JSON format
          </p>
        </div>
      </div>

      {/* Command Arguments */}
      <div className="space-y-3">
        <h5 className="text-xs font-semibold text-text-main">Command Arguments</h5>
        <div>
          <label className="block text-xs text-text-muted mb-1">Custom Arguments (one per line)</label>
          <textarea
            value={(provider.args || []).join('\n')}
            onChange={(e) => handleFieldChange('args', e.target.value.split('\n').filter(arg => arg.trim()))}
            className="w-full bg-black/30 text-text-main px-3 py-2 rounded border border-white/10 text-sm font-mono h-16"
            placeholder="--arg1 value1&#10;--arg2 value2"
          />
          <p className="text-[9px] text-text-dim mt-1">
            Custom command arguments (one per line). Use {'{model}'} and {'{prompt}'} placeholders.
          </p>
        </div>
      </div>
    </BaseProviderSettings>
  );
}
