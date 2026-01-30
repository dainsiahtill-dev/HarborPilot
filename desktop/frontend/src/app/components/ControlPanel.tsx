import { Anchor, Play, Square, Settings, FolderOpen, RefreshCw, Zap, Loader2, FastForward } from 'lucide-react';
import { useEffect, useState } from 'react';

interface ControlPanelProps {
  workspace: string;
  pmRunning: boolean;
  directorRunning: boolean;
  pmToggleDisabled?: boolean;
  directorToggleDisabled?: boolean;
  directorBlockedReason?: string;
  runOnceDisabled?: boolean;
  onOpenSettings: () => void;
  onWorkspaceCommit: (value: string) => void;
  onPickWorkspace?: () => void;
  onTogglePm: () => void;
  onRunPmOnce?: () => void;
  onResumePm?: () => void;
  onToggleDirector: () => void;
  onStopOllama?: () => void;
  onRefresh: () => void;
  workspaceError?: string | null;
  isStartingPM?: boolean;
  isStoppingPM?: boolean;
  isStartingDirector?: boolean;
  isStoppingDirector?: boolean;
  isStoppingOllama?: boolean;
}

export function ControlPanel({
  workspace,
  pmRunning,
  directorRunning,
  pmToggleDisabled,
  directorToggleDisabled,
  directorBlockedReason,
  runOnceDisabled,
  onOpenSettings,
  onWorkspaceCommit,
  onPickWorkspace,
  onTogglePm,
  onRunPmOnce,
  onResumePm,
  onToggleDirector,
  onStopOllama,
  onRefresh,
  workspaceError,
  isStartingPM,
  isStoppingPM,
  isStartingDirector,
  isStoppingDirector,
  isStoppingOllama,
}: ControlPanelProps) {
  const [workspaceInput, setWorkspaceInput] = useState(workspace);
  const pmDisabled = !!pmToggleDisabled;
  const directorDisabled = !!directorToggleDisabled;
  const runOnceBlocked = !!runOnceDisabled;

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
            disabled={pmDisabled || isStartingPM || isStoppingPM}
            className={`p-1.5 rounded transition-colors relative ${
              pmRunning
                ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                : 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
            } ${pmDisabled || isStartingPM || isStoppingPM ? 'opacity-50 cursor-not-allowed hover:bg-transparent' : ''}`}
            title={pmRunning ? 'Stop loop' : 'Start loop'}
          >
            {isStartingPM || isStoppingPM ? (
              <Loader2 className="size-4 animate-spin" />
            ) : pmRunning ? (
              <Square className="size-4" />
            ) : (
              <Play className="size-4" />
            )}
          </button>
          {onRunPmOnce ? (
            <button
              onClick={onRunPmOnce}
              disabled={runOnceBlocked || isStartingPM}
              className={`p-1.5 rounded transition-colors bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 relative ${
                runOnceBlocked || isStartingPM ? 'opacity-50 cursor-not-allowed hover:bg-transparent' : ''
              }`}
              title="Run once"
            >
              {isStartingPM ? <Loader2 className="size-4 animate-spin" /> : <Zap className="size-4" />}
            </button>
          ) : null}
          {onResumePm && !pmRunning ? (
            <button
              onClick={onResumePm}
              disabled={pmDisabled || isStartingPM || isStoppingPM}
              className={`p-1.5 rounded transition-colors bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 relative ${
                pmDisabled || isStartingPM || isStoppingPM ? 'opacity-50 cursor-not-allowed hover:bg-transparent' : ''
              }`}
              title="Resume last run"
            >
              <FastForward className="size-4" />
            </button>
          ) : null}
        </div>

        {/* Director 控制 */}
        <div className="flex items-center gap-2 px-3 py-1.5 bg-[#1e1e1e] rounded border border-gray-700">
          <span className="text-xs text-gray-400">Director</span>
          {directorBlockedReason ? (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-300">
              {directorBlockedReason}
            </span>
          ) : null}
          <button
            onClick={onToggleDirector}
            disabled={directorDisabled || isStartingDirector || isStoppingDirector}
            className={`p-1.5 rounded transition-colors relative ${
              directorRunning
                ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                : 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
            } ${directorDisabled || isStartingDirector || isStoppingDirector ? 'opacity-50 cursor-not-allowed hover:bg-transparent' : ''}`}
            title={directorBlockedReason || undefined}
          >
            {isStartingDirector || isStoppingDirector ? (
              <Loader2 className="size-4 animate-spin" />
            ) : directorRunning ? (
              <Square className="size-4" />
            ) : (
              <Play className="size-4" />
            )}
          </button>
        </div>

        {onStopOllama ? (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-[#1e1e1e] rounded border border-gray-700">
            <span className="text-xs text-gray-400">Ollama</span>
            <button
              onClick={onStopOllama}
              disabled={isStoppingOllama}
              className={`p-1.5 rounded transition-colors bg-red-500/20 text-red-400 hover:bg-red-500/30 relative ${
                isStoppingOllama ? 'opacity-50 cursor-not-allowed hover:bg-transparent' : ''
              }`}
              title="Stop running Ollama models"
            >
              {isStoppingOllama ? <Loader2 className="size-4 animate-spin" /> : <Square className="size-4" />}
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
        
        <div className="w-px h-8 bg-gray-700 mx-2" />
        
        <button
          onClick={() => window.dispatchEvent(new CustomEvent('open-intervention-center'))}
          className="relative p-2 text-gray-400 hover:text-gray-200 hover:bg-white/5 rounded transition-colors"
          title="Intervention Hub"
        >
          <ShieldAlert className="size-4 text-emerald-500" />
          {/* Badge for pending interventions - this would ideally be prop-driven */}
          <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full border border-[#252526]"></span>
        </button>
      </div>
    </header>
  );
}

// Helper icon component for ShieldAlert since it might not be imported
function ShieldAlert({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10" />
      <path d="M12 8v4" />
      <path d="M12 16h.01" />
    </svg>
  );
}
