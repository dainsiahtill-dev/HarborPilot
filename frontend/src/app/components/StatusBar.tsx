import { Activity, CheckCircle, Clock, AlertTriangle, Zap, FileText } from 'lucide-react';

interface StatusBarProps {
  pmRunning: boolean;
  directorRunning: boolean;
  pmStartedAt: number | null;
  directorStartedAt: number | null;
  pmMode?: string | null;
  failures: number | null;
  iteration: number | null;
  pmBackend: string;
  directorModel: string;
  backendError?: string | null;
  onOpenLogs?: () => void;
  gitPresent?: boolean | null;
  pmError?: string | null;
  directorError?: string | null;
  ollamaError?: string | null;
  successes?: number | null;
  total?: number | null;
  rate?: number | null;
  onPingHealth?: () => void;
  healthStatus?: string | null;
  lancedbOk?: boolean | null;
  lancedbError?: string | null;
}

function formatDuration(startedAt: number | null) {
  if (!startedAt) return '-';
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - startedAt));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
}

export function StatusBar({
  pmRunning,
  directorRunning,
  pmStartedAt,
  directorStartedAt,
  pmMode,
  failures,
  iteration,
  pmBackend,
  directorModel,
  backendError,
  onOpenLogs,
  gitPresent,
  pmError,
  directorError,
  ollamaError,
  successes,
  total,
  rate,
  onPingHealth,
  healthStatus,
  lancedbOk,
  lancedbError,
}: StatusBarProps) {
  const pmDuration = pmRunning ? formatDuration(pmStartedAt) : '-';
  const directorDuration = directorRunning ? formatDuration(directorStartedAt) : '-';
  const pmModeLabel = pmRunning && pmMode ? ` (${pmMode})` : '';
  const backendState = backendError ? 'Error' : 'OK';
  const backendClass = backendError ? 'text-red-400' : 'text-green-400';
  const gitState = gitPresent === null ? '未知' : gitPresent ? 'OK' : '缺失';
  const gitClass =
    gitPresent === null ? 'text-gray-500' : gitPresent ? 'text-green-400' : 'text-yellow-400';
  const lancedbState =
    lancedbOk === null || lancedbOk === undefined ? '未知' : lancedbOk ? 'OK' : '缺失';
  const lancedbClass =
    lancedbOk === null || lancedbOk === undefined
      ? 'text-gray-500'
      : lancedbOk
        ? 'text-green-400'
        : 'text-red-400';
  const successLabel =
    typeof successes === 'number' && typeof total === 'number'
      ? `${successes}/${total}${typeof rate === 'number' ? ` (${Math.round(rate * 100)}%)` : ''}`
      : '—';

  return (
    <div className="h-8 bg-bg-panel/30 backdrop-blur-md border-b border-white/5 flex items-center justify-between px-4 text-[10px] font-mono select-none">
      {/* 左侧：运行状态 */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 px-2 py-0.5 rounded-full bg-white/5 border border-white/5">
          <div
            className={`w-1.5 h-1.5 rounded-full shadow-[0_0_8px_currentColor] ${pmRunning ? 'bg-status-success text-status-success animate-pulse' : 'bg-text-dim text-text-dim'}`}
          />
          <span className="text-text-muted">
            PM <span className={pmRunning ? 'text-status-success' : ''}>{pmRunning ? `ACTV${pmModeLabel}` : 'IDLE'}</span>
          </span>
        </div>
        <div className="flex items-center gap-2 px-2 py-0.5 rounded-full bg-white/5 border border-white/5">
          <Activity className={`size-3 ${directorRunning ? 'text-status-secondary' : 'text-text-dim'}`} />
          <span className="text-text-muted">DIR <span className={directorRunning ? 'text-status-secondary' : ''}>{directorRunning ? 'ACTV' : 'IDLE'}</span></span>
        </div>
        <div className="w-px h-3 bg-white/10" />
        <div className="flex items-center gap-1.5 text-text-dim">
          <Clock className="size-3" />
          <span>{pmDuration}</span>
        </div>
        {pmError ? (
          <>
            <div className="w-px h-3 bg-white/10" />
            <span className="text-status-error font-bold flex items-center gap-1 animate-pulse">
              PM ERR: {pmError}
            </span>
          </>
        ) : null}
      </div>

      {/* 中间：统计信息 */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-1.5" title="Success Rate">
          <CheckCircle className="size-3 text-status-success drop-shadow-[0_0_5px_rgba(16,185,129,0.5)]" />
          <span className="text-text-main font-bold">{successLabel}</span>
        </div>
        <div className="flex items-center gap-1.5" title="Failures">
          <AlertTriangle className={`size-3 ${failures ? 'text-status-warning drop-shadow-[0_0_5px_rgba(245,158,11,0.5)]' : 'text-text-dim'}`} />
          <span className={failures ? 'text-status-warning' : 'text-text-dim'}>{failures ?? '0'}</span>
        </div>
        <div className="flex items-center gap-1.5" title="Iteration">
          <Zap className="size-3 text-accent drop-shadow-[0_0_5px_rgba(124,58,237,0.5)]" />
          <span className="text-text-main">{iteration ?? '-'}</span>
        </div>
      </div>

      {/* 右侧：后端信息 */}
      <div className="flex items-center gap-3 text-text-muted">
        <span className="px-1.5 py-0.5 rounded bg-white/5">PM[{pmBackend || '-'}]</span>
        <span className="text-white/10">/</span>
        <span className="px-1.5 py-0.5 rounded bg-white/5">DIR[{directorModel || '-'}]</span>
        <span className="text-white/10">/</span>
        <div className="flex items-center gap-1.5 px-1.5 py-0.5 rounded bg-white/5">
          <span>LANCE</span>
          <span className={`w-1.5 h-1.5 rounded-full shadow-[0_0_5px_currentColor] ${lancedbOk ? 'bg-status-success text-status-success' : 'bg-status-error text-status-error'}`} title={lancedbError || undefined}></span>
        </div>
        <span className="text-white/10">|</span>
        <div className="flex items-center gap-1.5 px-1.5 py-0.5 rounded bg-white/5">
          <span>GIT</span>
          <span className={`w-1.5 h-1.5 rounded-full shadow-[0_0_5px_currentColor] ${gitPresent ? 'bg-status-success text-status-success' : 'bg-status-warning text-status-warning'}`}></span>
        </div>

        {onPingHealth ? (
          <>
            <span className="text-white/10">|</span>
            <button
              onClick={onPingHealth}
              className="inline-flex items-center gap-1 text-text-muted hover:text-accent transition-colors px-1.5 py-0.5 rounded hover:bg-white/5"
            >
              <Activity className="size-3" />
              <span>{healthStatus || 'PING'}</span>
            </button>
          </>
        ) : null}
        {onOpenLogs ? (
          <>
            <span className="text-white/10">|</span>
            <button
              onClick={onOpenLogs}
              className="inline-flex items-center gap-1 text-text-muted hover:text-accent transition-colors px-1.5 py-0.5 rounded hover:bg-white/5"
            >
              <FileText className="size-3" />
              <span>LOGS</span>
            </button>
          </>
        ) : null}
      </div>
    </div>
  );
}
