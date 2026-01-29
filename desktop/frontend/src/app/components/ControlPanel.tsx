import { Anchor, Play, Square, Settings, FolderOpen, RefreshCw, Zap } from 'lucide-react';
import { useEffect, useState } from 'react';

interface ControlPanelProps {
  workspace: string;
  pmRunning: boolean;
  directorRunning: boolean;
  onOpenSettings: () => void;
  onWorkspaceCommit: (value: string) => void;
  onPickWorkspace?: () => void;
  onTogglePm: () => void;
  onRunPmOnce?: () => void;
  onToggleDirector: () => void;
  onStopOllama?: () => void;
  onRefresh: () => void;
  workspaceError?: string | null;
}

export function ControlPanel({
  workspace,
  pmRunning,
  directorRunning,
  onOpenSettings,
  onWorkspaceCommit,
  onPickWorkspace,
  onTogglePm,
  onRunPmOnce,
  onToggleDirector,
  onStopOllama,
  onRefresh,
  workspaceError,
}: ControlPanelProps) {
  const [workspaceInput, setWorkspaceInput] = useState(workspace);

  useEffect(() => {
    setWorkspaceInput(workspace);
  }, [workspace]);

  const commitWorkspace = () => {
    const next = workspaceInput.trim();
    if (next && next !== workspace) {
      onWorkspaceCommit(next);
    }
  };

  return (
    <header className="h-14 bg-[#252526] border-b border-gray-800 flex items-center justify-between px-4">
      {/* Logo 和标题 */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Anchor className="size-7 text-blue-400" />
          <div>
            <h1 className="font-bold text-lg text-gray-100">HarborPilot</h1>
            <p className="text-xs text-gray-500">无人值守 AI 代码协作</p>
          </div>
        </div>
      </div>

      {/* Workspace */}
      <div className="flex-1 max-w-md mx-8 relative">
        <div
          className={`flex items-center gap-2 bg-[#1e1e1e] rounded px-3 py-1.5 border ${
            workspaceError ? 'border-red-500/60' : 'border-gray-700'
          }`}
          title={workspaceError || undefined}
        >
          {onPickWorkspace ? (
            <button
              type="button"
              onClick={onPickWorkspace}
              className="text-gray-400 hover:text-gray-200 transition-colors"
              aria-label="选择 Workspace"
              title="选择 Workspace"
            >
              <FolderOpen className="size-4" />
            </button>
          ) : (
            <FolderOpen className="size-4 text-gray-400" />
          )}
          <input
            type="text"
            value={workspaceInput}
            onChange={(e) => setWorkspaceInput(e.target.value)}
            onBlur={commitWorkspace}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                commitWorkspace();
              }
            }}
            className="flex-1 bg-transparent text-sm text-gray-300 outline-none"
            placeholder="Workspace path"
            aria-invalid={workspaceError ? true : undefined}
            aria-describedby={workspaceError ? 'workspace-error' : undefined}
          />
        </div>
        {workspaceError ? (
          <div
            id="workspace-error"
            className="absolute left-0 right-0 top-full mt-1 text-xs text-red-300 bg-[#1e1e1e] border border-red-500/40 rounded px-2 py-1"
          >
            {workspaceError}
          </div>
        ) : null}
      </div>

      {/* 控制按钮 */}
      <div className="flex items-center gap-2">
        {/* PM 控制 */}
        <div className="flex items-center gap-2 px-3 py-1.5 bg-[#1e1e1e] rounded border border-gray-700">
          <span className="text-xs text-gray-400">PM</span>
          <button
            onClick={onTogglePm}
            className={`p-1.5 rounded transition-colors ${
              pmRunning
                ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                : 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
            }`}
            title={pmRunning ? 'Stop loop' : 'Start loop'}
          >
            {pmRunning ? <Square className="size-4" /> : <Play className="size-4" />}
          </button>
          {onRunPmOnce ? (
            <button
              onClick={onRunPmOnce}
              className="p-1.5 rounded transition-colors bg-blue-500/20 text-blue-400 hover:bg-blue-500/30"
              title="Run once"
              disabled={pmRunning}
            >
              <Zap className="size-4" />
            </button>
          ) : null}
        </div>

        {/* Director 控制 */}
        <div className="flex items-center gap-2 px-3 py-1.5 bg-[#1e1e1e] rounded border border-gray-700">
          <span className="text-xs text-gray-400">Director</span>
          <button
            onClick={onToggleDirector}
            className={`p-1.5 rounded transition-colors ${
              directorRunning
                ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                : 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
            }`}
          >
            {directorRunning ? <Square className="size-4" /> : <Play className="size-4" />}
          </button>
        </div>

        {onStopOllama ? (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-[#1e1e1e] rounded border border-gray-700">
            <span className="text-xs text-gray-400">Ollama</span>
            <button
              onClick={onStopOllama}
              className="p-1.5 rounded transition-colors bg-red-500/20 text-red-400 hover:bg-red-500/30"
              title="Stop running Ollama models"
            >
              <Square className="size-4" />
            </button>
          </div>
        ) : null}

        <div className="w-px h-8 bg-gray-700" />

        <button
          className="p-2 text-gray-400 hover:text-gray-200 hover:bg-white/5 rounded transition-colors"
          onClick={onRefresh}
        >
          <RefreshCw className="size-4" />
        </button>

        <button
          onClick={onOpenSettings}
          className="p-2 text-gray-400 hover:text-gray-200 hover:bg-white/5 rounded transition-colors"
        >
          <Settings className="size-4" />
        </button>
      </div>
    </header>
  );
}
