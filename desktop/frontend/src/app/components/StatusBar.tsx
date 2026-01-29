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
  const gitState = gitPresent === null ? 'Unknown' : gitPresent ? 'OK' : 'Missing';
  const gitClass =
    gitPresent === null ? 'text-gray-500' : gitPresent ? 'text-green-400' : 'text-yellow-400';
  const lancedbState =
    lancedbOk === null || lancedbOk === undefined ? 'Unknown' : lancedbOk ? 'OK' : 'Missing';
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
    <div className="h-8 bg-[#252526] border-t border-gray-800 flex items-center justify-between px-4 text-xs">
      {/* 左侧：运行状态 */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <div
            className={`w-2 h-2 rounded-full ${pmRunning ? 'bg-green-400 animate-pulse' : 'bg-gray-600'}`}
          />
          <span className="text-gray-400">
            PM: {pmRunning ? `Running${pmModeLabel}` : 'Idle'}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <Activity className="size-3 text-purple-400" />
          <span className="text-gray-400">Director: {directorRunning ? 'Running' : 'Idle'}</span>
        </div>
        <div className="w-px h-4 bg-gray-700" />
        <div className="flex items-center gap-1.5">
          <Clock className="size-3 text-gray-500" />
          <span className="text-gray-400">运行时长: {pmDuration}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Clock className="size-3 text-gray-500" />
          <span className="text-gray-400">Director 时长: {directorDuration}</span>
        </div>
        {pmError ? (
          <>
            <div className="w-px h-4 bg-gray-700" />
            <span className="text-red-400">PM 错误: {pmError}</span>
          </>
        ) : null}
        {directorError ? (
          <>
            <div className="w-px h-4 bg-gray-700" />
            <span className="text-red-400">Director 错误: {directorError}</span>
          </>
        ) : null}
        {ollamaError ? (
          <>
            <div className="w-px h-4 bg-gray-700" />
            <span className="text-red-400">Ollama 错误: {ollamaError}</span>
          </>
        ) : null}
      </div>

      {/* 中间：统计信息 */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <CheckCircle className="size-3 text-green-400" />
          <span className="text-gray-400">成功: {successLabel}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <AlertTriangle className="size-3 text-yellow-400" />
          <span className="text-gray-400">重试: {failures ?? '—'}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Zap className="size-3 text-blue-400" />
          <span className="text-gray-400">迭代: {iteration ?? '—'}</span>
        </div>
      </div>

      {/* 右侧：后端信息 */}
      <div className="flex items-center gap-4">
        <span className="text-gray-500">PM: {pmBackend || '-'}</span>
        <span className="text-gray-500">|</span>
        <span className="text-gray-500">Director: {directorModel || '-'}</span>
        <span className="text-gray-500">|</span>
        <span className="text-gray-500">Memory: LanceDB</span>
        <span className={lancedbClass} title={lancedbError || undefined}>
          {lancedbState}
        </span>
        <span className="text-gray-500">|</span>
        <span className={backendClass}>Backend: {backendState}</span>
        <span className="text-gray-500">|</span>
        <span className={gitClass}>Git: {gitState}</span>
        {onPingHealth ? (
          <>
            <span className="text-gray-500">|</span>
            <button
              onClick={onPingHealth}
              className="inline-flex items-center gap-1 text-gray-400 hover:text-gray-200 transition-colors"
            >
              <Activity className="size-3" />
              <span>Ping</span>
            </button>
            {healthStatus ? (
              <span className="text-gray-500">{healthStatus}</span>
            ) : null}
          </>
        ) : null}
        {onOpenLogs ? (
          <>
            <span className="text-gray-500">|</span>
            <button
              onClick={onOpenLogs}
              className="inline-flex items-center gap-1 text-gray-400 hover:text-gray-200 transition-colors"
            >
              <FileText className="size-3" />
              <span>日志</span>
            </button>
          </>
        ) : null}
      </div>
    </div>
  );
}
