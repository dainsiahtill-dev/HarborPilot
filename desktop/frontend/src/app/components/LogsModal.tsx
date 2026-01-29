import { RefreshCw, X, FileText, Activity } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch, connectWebSocket } from '@/api';

interface LogsModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialSourceId?: string | null;
  banner?: string | null;
  onDismissBanner?: () => void;
}

const LOG_SOURCES = [
  { id: 'pm-subprocess', label: 'PM Subprocess', path: 'state/ollama/PM_SUBPROCESS.log', channel: 'pm_subprocess' },
  { id: 'pm-report', label: 'PM Report', path: 'state/ollama/PM_REPORT.md', channel: 'pm_report' },
  { id: 'pm-log', label: 'PM Log (jsonl)', path: 'state/ollama/PM_LOG.jsonl', channel: 'pm_log' },
  { id: 'director', label: 'Director Subprocess', path: 'state/ollama/DIRECTOR_SUBPROCESS.log', channel: 'director_console' },
  { id: 'planner', label: 'Planner', path: 'state/ollama/PLANNER_RESPONSE.md', channel: 'planner' },
  { id: 'ollama', label: 'Ollama', path: 'state/ollama/OLLAMA_RESPONSE.md', channel: 'ollama' },
  { id: 'qa', label: 'QA', path: 'state/ollama/QA_RESPONSE.md', channel: 'qa' },
  { id: 'runlog', label: 'RunLog', path: 'state/ollama/RUNLOG.md', channel: 'runlog' },
];

export function LogsModal({
  isOpen,
  onClose,
  initialSourceId,
  banner,
  onDismissBanner,
}: LogsModalProps) {
  const [active, setActive] = useState(LOG_SOURCES[0].id);
  const [lines, setLines] = useState<string[]>([]);
  const [mtime, setMtime] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);

  const activeSource = useMemo(
    () => LOG_SOURCES.find((item) => item.id === active) || LOG_SOURCES[0],
    [active]
  );

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/files/read?path=${encodeURIComponent(activeSource.path)}&tail_lines=400`);
      if (!res.ok) {
        throw new Error('Failed to load log');
      }
      const payload = (await res.json()) as { content?: string; mtime?: string };
      setLines(payload.content ? payload.content.split('\n') : []);
      setMtime(payload.mtime || '');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load log');
      setLines([]);
      setMtime('');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isOpen) return;
    refresh();
  }, [isOpen, active]);

  useEffect(() => {
    if (!isOpen) return;
    if (initialSourceId) {
      const exists = LOG_SOURCES.some((item) => item.id === initialSourceId);
      setActive(exists ? initialSourceId : LOG_SOURCES[0].id);
    }
  }, [isOpen, initialSourceId]);

  useEffect(() => {
    if (!isOpen) return;
    let activeSocket: WebSocket | null = null;
    let alive = true;

    const connect = async () => {
      try {
        activeSocket = await connectWebSocket();
      } catch {
        if (alive) setLive(false);
        return;
      }

      socketRef.current = activeSocket;
      if (!alive) return;

      activeSocket.onopen = () => {
        setLive(true);
        activeSocket?.send(
          JSON.stringify({
            type: 'subscribe',
            channels: [activeSource.channel],
            tail_lines: 200,
          })
        );
      };

      activeSocket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.channel !== activeSource.channel) return;
          if (payload.type === 'snapshot' && Array.isArray(payload.lines)) {
            setLines(payload.lines);
            return;
          }
          if (payload.type === 'line' && payload.text) {
            setLines((prev) => [...prev, payload.text].slice(-1000));
          }
        } catch {
          // ignore malformed payloads
        }
      };

      activeSocket.onclose = () => {
        if (alive) setLive(false);
      };

      activeSocket.onerror = () => {
        if (alive) setLive(false);
      };
    };

    connect();

    return () => {
      alive = false;
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [isOpen, activeSource.channel]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[#252526] border border-gray-700 rounded-lg w-full max-w-3xl max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <div className="flex items-center gap-2">
            <FileText className="size-4 text-blue-400" />
            <h2 className="text-lg font-semibold text-gray-200">运行日志</h2>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={refresh}
              className="p-2 text-gray-400 hover:text-gray-200 hover:bg-white/5 rounded transition-colors"
              disabled={loading}
            >
              <RefreshCw className="size-4" />
            </button>
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-gray-200 hover:bg-white/5 rounded transition-colors"
            >
              <X className="size-4" />
            </button>
          </div>
        </div>

        {banner ? (
          <div className="mx-4 mt-3 max-h-40 overflow-auto rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200 whitespace-pre-wrap">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1">{banner}</div>
              {onDismissBanner ? (
                <button
                  onClick={onDismissBanner}
                  className="ml-2 text-red-200/70 hover:text-red-100 transition-colors"
                  aria-label="Dismiss"
                >
                  <X className="size-4" />
                </button>
              ) : null}
            </div>
          </div>
        ) : null}

        <div className="px-4 pt-3">
          <div className="flex items-center gap-2">
            {LOG_SOURCES.map((item) => (
              <button
                key={item.id}
                onClick={() => setActive(item.id)}
                className={`px-3 py-1.5 text-sm rounded transition-colors ${
                  active === item.id
                    ? 'bg-blue-500/20 text-blue-300'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {item.label}
              </button>
            ))}
            <span className="ml-auto text-xs text-gray-500">更新时间: {mtime || '-'}</span>
            <span className="text-xs text-gray-500 flex items-center gap-1">
              <Activity className="size-3" />
              {live ? '实时' : '离线'}
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-4">
          {error ? (
            <div className="text-sm text-red-300">{error}</div>
          ) : (
            <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap">
              {loading ? '加载中...' : lines.join('\n') || '(空)'}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
