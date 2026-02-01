import { Anchor, Play, Square, Settings, FolderOpen, RefreshCw, Zap, Loader2, FastForward, FileText } from 'lucide-react';
import { useEffect, useState } from 'react';
import { WindowControls } from './WindowControls';

interface ControlPanelProps {
  workspace: string;
  pmRunning: boolean;
  directorRunning: boolean;
  pmToggleDisabled?: boolean;
  directorToggleDisabled?: boolean;
  directorBlockedReason?: string;
  runOnceDisabled?: boolean;
  agentsNeeded?: boolean;
  agentsDraftReady?: boolean;
  agentsDraftFailed?: boolean;
  onOpenAgentsReview?: () => void;
  onGenerateAgentsDraft?: () => void;
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
  agentsNeeded,
  agentsDraftReady,
  agentsDraftFailed,
  onOpenAgentsReview,
  onGenerateAgentsDraft,
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
  const showAgents = !!agentsNeeded;
  const agentsReady = !!agentsDraftReady || !!agentsDraftFailed;

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
    <header className="panel-header z-50 relative">
      {/* Logo 和标题 */}
      <div className="flex items-center gap-4">
        <WindowControls />
        <div className="w-px h-4 bg-white/10" />
        <div className="flex items-center gap-2 group">
          <div className="relative">
            <div className="absolute inset-0 bg-accent blur-md opacity-20 group-hover:opacity-40 transition-opacity"></div>
            <Anchor className="size-6 text-accent relative z-10" />
          </div>
          <div>
            <h1 className="font-heading font-bold text-xl text-text-main tracking-tight">HarborPilot</h1>
            <p className="text-[10px] text-text-dim font-mono tracking-wider uppercase">AI Co-Pilot</p>
          </div>
        </div>
      </div>

      {/* Workspace */}
      <div className="flex-1 max-w-lg mx-8 relative group">
        <div
          className={`no-drag flex items-center gap-2 bg-bg-panel/50 backdrop-blur-sm rounded-lg px-3 py-1.5 border transition-all duration-300 ${workspaceError ? 'border-status-error/60 shadow-[0_0_10px_rgba(239,68,68,0.2)]' : 'border-white/10 group-hover:border-accent/30 group-hover:shadow-glow'
            }`}
          title={workspaceError || undefined}
        >
          {onPickWorkspace ? (
            <button
              type="button"
              onClick={onPickWorkspace}
              className="text-text-muted hover:text-accent transition-colors"
              aria-label="选择 Workspace"
              title="选择 Workspace"
            >
              <FolderOpen className="size-4" />
            </button>
          ) : (
            <FolderOpen className="size-4 text-text-dim" />
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
            className="flex-1 bg-transparent text-sm text-text-main outline-none font-sans placeholder:text-text-dim/50"
            placeholder="Select a workspace..."
            aria-invalid={workspaceError ? true : undefined}
            aria-describedby={workspaceError ? 'workspace-error' : undefined}
          />
        </div>
        {workspaceError ? (
          <div
            id="workspace-error"
            className="absolute left-0 right-0 top-full mt-1 text-xs text-status-error bg-bg-panel border border-status-error/30 rounded px-2 py-1 shadow-lg z-50 backdrop-blur-md"
          >
            {workspaceError}
          </div>
        ) : null}
      </div>

      {/* 控制按钮 */}
      <div className="flex items-center gap-3">
        {/* PM 控制 */}
        <div className="flex items-center gap-1.5 px-2 py-1 bg-white/5 rounded-lg border border-white/5 backdrop-blur-sm">
          <span className="text-[10px] uppercase font-bold text-text-dim tracking-wider px-1">PM</span>
          <button
            onClick={onTogglePm}
            disabled={pmDisabled || isStartingPM || isStoppingPM}
            className={`p-1.5 rounded-md transition-all duration-300 relative ${pmRunning
              ? 'bg-gradient-primary text-white shadow-glow'
              : 'bg-white/5 text-text-muted hover:bg-white/10 hover:text-text-main'
              } ${pmDisabled || isStartingPM || isStoppingPM ? 'opacity-50 cursor-not-allowed hover:bg-transparent' : ''}`}
            title={pmRunning ? '停止循环' : '启动循环'}
          >
            {isStartingPM || isStoppingPM ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : pmRunning ? (
              <Square className="size-3.5 fill-current" />
            ) : (
              <Play className="size-3.5 fill-current" />
            )}
          </button>
          {onRunPmOnce ? (
            <button
              onClick={onRunPmOnce}
              disabled={runOnceBlocked || isStartingPM}
              className={`p-1.5 rounded-md transition-colors text-text-muted hover:text-accent hover:bg-accent-dim relative ${runOnceBlocked || isStartingPM ? 'opacity-50 cursor-not-allowed hover:bg-transparent' : ''
                }`}
              title="运行一次"
            >
              {isStartingPM ? <Loader2 className="size-3.5 animate-spin" /> : <Zap className="size-3.5" />}
            </button>
          ) : null}
          {onResumePm && !pmRunning ? (
            <button
              onClick={onResumePm}
              disabled={pmDisabled || isStartingPM || isStoppingPM}
              className={`p-1.5 rounded-md transition-colors text-text-muted hover:text-status-warning hover:bg-status-warning/10 relative ${pmDisabled || isStartingPM || isStoppingPM ? 'opacity-50 cursor-not-allowed hover:bg-transparent' : ''
                }`}
              title="恢复上次运行"
            >
              <FastForward className="size-3.5" />
            </button>
          ) : null}
        </div>

        {/* Director 控制 */}
        <div className="flex items-center gap-1.5 px-2 py-1 bg-white/5 rounded-lg border border-white/5 backdrop-blur-sm">
          <span className="text-[10px] uppercase font-bold text-text-dim tracking-wider px-1">Director</span>
          {directorBlockedReason ? (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-status-error/20 text-status-error border border-status-error/20">
              {directorBlockedReason}
            </span>
          ) : null}
          <button
            onClick={onToggleDirector}
            disabled={directorDisabled || isStartingDirector || isStoppingDirector}
            className={`p-1.5 rounded-md transition-all duration-300 relative ${directorRunning
              ? 'bg-gradient-to-r from-accent-secondary to-blue-600 text-white shadow-[0_0_15px_rgba(6,182,212,0.4)]'
              : 'bg-white/5 text-text-muted hover:bg-white/10 hover:text-text-main'
              } ${directorDisabled || isStartingDirector || isStoppingDirector ? 'opacity-50 cursor-not-allowed hover:bg-transparent' : ''}`}
            title={directorBlockedReason || undefined}
          >
            {isStartingDirector || isStoppingDirector ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : directorRunning ? (
              <Square className="size-3.5 fill-current" />
            ) : (
              <Play className="size-3.5 fill-current" />
            )}
          </button>
        </div>

        {showAgents ? (
          <div className="flex items-center gap-1.5 px-2 py-1 bg-white/5 rounded-lg border border-status-warning/30 backdrop-blur-sm">
            <span className="text-[10px] uppercase font-bold text-status-warning tracking-wider px-1">AGENTS</span>
            <button
              onClick={agentsReady ? onOpenAgentsReview : onGenerateAgentsDraft}
              disabled={agentsReady ? !onOpenAgentsReview : !onGenerateAgentsDraft}
              className={`p-1.5 rounded-md transition-colors relative ${agentsReady
                ? 'bg-status-warning/20 text-status-warning hover:bg-status-warning/30'
                : 'bg-accent/20 text-accent hover:bg-accent/30'
                } ${(!onOpenAgentsReview && agentsReady) || (!onGenerateAgentsDraft && !agentsReady) ? 'opacity-50 cursor-not-allowed hover:bg-transparent' : ''}`}
              title={agentsReady ? '打开 AGENTS 审阅' : '生成 AGENTS 草稿'}
            >
              <FileText className="size-3.5" />
            </button>
          </div>
        ) : null}

        {onStopOllama ? (
          <div className="flex items-center gap-1.5 px-2 py-1 bg-white/5 rounded-lg border border-white/5 backdrop-blur-sm">
            <span className="text-[10px] uppercase font-bold text-text-dim tracking-wider px-1">Ollama</span>
            <button
              onClick={onStopOllama}
              disabled={isStoppingOllama}
              className={`p-1.5 rounded-md transition-colors bg-status-error/10 text-status-error hover:bg-status-error/20 relative ${isStoppingOllama ? 'opacity-50 cursor-not-allowed hover:bg-transparent' : ''
                }`}
              title="停止 Ollama 模型"
            >
              {isStoppingOllama ? <Loader2 className="size-3.5 animate-spin" /> : <Square className="size-3.5" />}
            </button>
          </div>
        ) : null}

        <div className="w-px h-6 bg-white/10 mx-1" />

        <button
          className="btn-icon"
          onClick={onRefresh}
        >
          <RefreshCw className="size-4" />
        </button>

        <button
          onClick={onOpenSettings}
          className="btn-icon"
        >
          <Settings className="size-4" />
        </button>

        <div className="w-px h-6 bg-white/10 mx-1" />

        <button
          onClick={() => window.dispatchEvent(new CustomEvent('open-intervention-center'))}
          className="relative btn-icon group"
          title="干预中心"
        >
          <div className="absolute inset-0 bg-status-error/20 blur-sm rounded-full opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <ShieldAlert className="size-4 text-status-error relative z-10" />
          {/* Badge for pending interventions - this would ideally be prop-driven */}
          <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-status-error rounded-full ring-2 ring-bg-panel"></span>
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
