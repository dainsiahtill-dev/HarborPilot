import { RefreshCw, X, FileText, Activity, AlertTriangle, TerminalSquare, Wrench } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch, connectWebSocket } from '@/api';
import { CodexCliStreamParser, parseCodexCliLines, type LogEvent } from '@/app/components/logs/CodexCliStreamParser';

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

function SmartText({ text }: { text: string }) {
  const max = 400;
  if (text.length <= max) {
    return <div className="text-xs text-gray-200 whitespace-pre-wrap">{text}</div>;
  }
  return (
    <details className="text-xs text-gray-200 whitespace-pre-wrap">
      <summary className="cursor-pointer text-gray-400">展开内容</summary>
      {text}
    </details>
  );
}

const ROLE_BADGE_STYLES: Record<'user' | 'thinking' | 'exec', string> = {
  user: 'border-blue-500/40 bg-blue-500/20 text-blue-200',
  thinking: 'border-purple-500/40 bg-purple-500/20 text-purple-200',
  exec: 'border-amber-500/40 bg-amber-500/20 text-amber-200',
};

function RoleBadge({ role }: { role: 'user' | 'thinking' | 'exec' }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${ROLE_BADGE_STYLES[role]}`}
    >
      {role}
    </span>
  );
}

type MarkupKind = 'html' | 'svg' | 'xml';
type MarkupView = 'render' | 'source' | 'tree';
type XmlTreeNode = {
  name: string;
  attributes: [string, string][];
  children: XmlTreeNode[];
  text?: string;
};

function detectMarkupKind(source: string, pathHint?: string): MarkupKind | null {
  if (!source) return null;
  const hint = (pathHint || '').toLowerCase();
  if (hint.endsWith('.vue')) return null;
  if (hint.endsWith('.svg')) return 'svg';
  if (hint.endsWith('.html') || hint.endsWith('.htm')) return 'html';
  if (hint.endsWith('.xml')) return 'xml';
  const trimmed = source.trim();
  if (!trimmed.startsWith('<')) return null;
  if (/^<!doctype\s+html/i.test(trimmed) || /<html[\s>]/i.test(trimmed)) return 'html';
  if (/<svg[\s>]/i.test(trimmed)) return 'svg';
  if (/^<\?xml/i.test(trimmed)) return 'xml';
  if (/<[a-zA-Z][\w:-]*[^>]*>/.test(trimmed) && /<\/[a-zA-Z][\w:-]*>/.test(trimmed)) return 'html';
  if (typeof window !== 'undefined' && 'DOMParser' in window) {
    try {
      const parser = new DOMParser();
      const xml = parser.parseFromString(trimmed, 'text/xml');
      if (!xml.querySelector('parsererror')) return 'xml';
    } catch {
      // ignore parse failures
    }
  }
  return null;
}

function MarkupCard({
  title,
  source,
  kind,
  badge,
  meta,
}: {
  title: string;
  source: string;
  kind: MarkupKind;
  badge?: JSX.Element | null;
  meta?: string;
}) {
  const [view, setView] = useState<MarkupView>(kind === 'xml' ? 'tree' : 'render');
  const canRender = kind === 'html' || kind === 'svg';
  const canTree = kind === 'xml';
  const xmlTree = useMemo(() => {
    if (!canTree) return null;
    try {
      const parser = new DOMParser();
      const xml = parser.parseFromString(source, 'text/xml');
      if (xml.querySelector('parsererror')) return null;
      const root = xml.documentElement;
      return root ? buildXmlTree(root) : null;
    } catch {
      return null;
    }
  }, [canTree, source]);
  const srcDoc = useMemo(() => {
    if (!canRender) return '';
    if (kind === 'html') return source.trim();
    if (kind === 'svg') {
      return `<!doctype html><html><body style="margin:0;display:flex;align-items:center;justify-content:center;background:#111827;">${source.trim()}</body></html>`;
    }
    return '';
  }, [canRender, kind, source]);

  return (
    <div className="rounded border border-gray-700 bg-gray-900/40 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-gray-400">
          {badge}
          <span>{title}</span>
          <span className="rounded bg-gray-800 px-2 py-0.5 text-[10px] text-gray-300 uppercase">{kind}</span>
          {meta ? <span className="text-gray-500">{meta}</span> : null}
        </div>
        <div className="flex items-center gap-1 text-[10px]">
          {canRender ? (
            <button
              className={`rounded px-2 py-0.5 ${view === 'render' ? 'bg-blue-500/30 text-blue-200' : 'text-gray-400 hover:text-gray-200'}`}
              onClick={() => setView('render')}
            >
              Render
            </button>
          ) : null}
          {canTree ? (
            <button
              className={`rounded px-2 py-0.5 ${view === 'tree' ? 'bg-blue-500/30 text-blue-200' : 'text-gray-400 hover:text-gray-200'}`}
              onClick={() => setView('tree')}
            >
              Tree
            </button>
          ) : null}
          <button
            className={`rounded px-2 py-0.5 ${view === 'source' ? 'bg-blue-500/30 text-blue-200' : 'text-gray-400 hover:text-gray-200'}`}
            onClick={() => setView('source')}
          >
            Source
          </button>
        </div>
      </div>
      {view === 'render' && canRender ? (
        <iframe
          className="mt-2 h-60 w-full rounded border border-gray-700 bg-white"
          sandbox=""
          srcDoc={srcDoc}
          title={title}
        />
      ) : view === 'tree' && canTree ? (
        xmlTree ? (
          <div className="mt-2">
            <XmlTreeNodeView node={xmlTree} depth={0} />
          </div>
        ) : (
          <pre className="mt-2 text-xs text-gray-200 whitespace-pre-wrap">{source || '(empty)'}</pre>
        )
      ) : (
        <pre className="mt-2 text-xs text-gray-200 whitespace-pre-wrap">{source || '(empty)'}</pre>
      )}
    </div>
  );
}

function buildXmlTree(node: Node): XmlTreeNode | null {
  if (node.nodeType === Node.TEXT_NODE || node.nodeType === Node.CDATA_SECTION_NODE) {
    const text = (node.textContent || '').trim();
    if (!text) return null;
    return { name: '#text', attributes: [], children: [], text };
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return null;
  const el = node as Element;
  const attributes: [string, string][] = Array.from(el.attributes).map((attr) => [attr.name, attr.value]);
  const children: XmlTreeNode[] = [];
  Array.from(el.childNodes).forEach((child) => {
    const childNode = buildXmlTree(child);
    if (childNode) children.push(childNode);
  });
  return {
    name: el.tagName,
    attributes,
    children,
  };
}

function XmlTreeNodeView({ node, depth }: { node: XmlTreeNode; depth: number }) {
  const isText = node.name === '#text';
  if (isText) {
    return (
      <div className="ml-4 text-xs text-gray-300 italic whitespace-pre-wrap">{node.text}</div>
    );
  }
  const openByDefault = depth < 1;
  return (
    <details open={openByDefault} className="text-xs text-gray-200">
      <summary className="cursor-pointer text-gray-200">
        <span className="text-blue-200">&lt;{node.name}</span>
        {node.attributes.length
          ? node.attributes.map(([key, value]) => (
              <span key={key} className="ml-1 text-emerald-200">
                {key}="<span className="text-gray-300">{value}</span>"
              </span>
            ))
          : null}
        <span className="text-blue-200">&gt;</span>
      </summary>
      <div className="ml-4 space-y-1">
        {node.children.map((child, idx) => (
          <XmlTreeNodeView key={`${child.name}-${idx}`} node={child} depth={depth + 1} />
        ))}
        <div className="text-blue-200">&lt;/{node.name}&gt;</div>
      </div>
    </details>
  );
}

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
  const [viewMode, setViewMode] = useState<'raw' | 'smart' | 'json'>('smart');
  const [filter, setFilter] = useState<'all' | 'error' | 'exec' | 'tool'>('all');
  const [query, setQuery] = useState('');
  const socketRef = useRef<WebSocket | null>(null);
  const [streamEvents, setStreamEvents] = useState<LogEvent[]>([]);
  const parserRef = useRef<CodexCliStreamParser | null>(null);

  const activeSource = useMemo(
    () => LOG_SOURCES.find((item) => item.id === active) || LOG_SOURCES[0],
    [active]
  );

  const allowSmart = active === 'pm-subprocess';
  const allowJson = active === 'pm-log';
  const allowRaw = active !== 'pm-log';

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
    if (active === 'pm-subprocess') {
      setViewMode('smart');
    } else if (active === 'pm-log') {
      setViewMode('json');
    } else {
      setViewMode('raw');
    }
  }, [isOpen, active]);

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
            const parser = new CodexCliStreamParser();
            payload.lines.forEach((line: string) => parser.feedLine(line));
            parserRef.current = parser;
            setStreamEvents([...parser.events]);
            return;
          }
          if (payload.type === 'line' && payload.text) {
            setLines((prev) => [...prev, payload.text].slice(-1000));
            if (!parserRef.current) parserRef.current = new CodexCliStreamParser();
            parserRef.current.feedLine(payload.text);
            setStreamEvents([...parserRef.current.events]);
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

  const smartEvents = useMemo(() => {
    if (streamEvents.length > 0) return streamEvents;
    return parseCodexCliLines(lines);
  }, [lines, streamEvents]);
  const jsonEvents = useMemo(() => {
    if (active !== 'pm-log') return [];
    return lines
      .map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) return null;
        try {
          return { id: `jsonl-${idx}`, raw: trimmed, value: JSON.parse(trimmed) };
        } catch {
          return { id: `jsonl-${idx}`, raw: trimmed, value: null };
        }
      })
      .filter(Boolean) as { id: string; raw: string; value: unknown | null }[];
  }, [active, lines]);

  const isEmptyJson = (value: unknown, raw?: string) => {
    if (value == null) return !(raw && raw.trim());
    if (Array.isArray(value)) return value.length === 0;
    if (typeof value === 'object') return Object.keys(value as Record<string, unknown>).length === 0;
    return false;
  };

  const filteredEvents = useMemo(() => {
    return smartEvents.filter((event) => {
      if (filter !== 'all' && event.kind !== filter) {
        return false;
      }
      if (!query.trim()) return true;
      const haystack =
        event.kind === 'json'
          ? event.raw
          : event.kind === 'error'
            ? event.raw
            : event.kind === 'section'
              ? `${event.title}\n${event.body}`
              : event.kind === 'exec'
                ? `${event.cmd} ${event.cwd ?? ''}`
                : event.kind === 'tool'
                  ? `${event.tool} ${event.message ?? ''}`
                    : event.kind === 'thinking'
                      ? `${event.title}\n${event.body}`
                    : event.kind === 'runStart'
                      ? `${event.version} ${Object.values(event.meta).join(' ')}`
                      : event.kind === 'role'
                        ? event.role
                        : event.kind === 'command'
                          ? `${event.shell} ${event.cmd}`
                          : event.kind === 'commandResult'
                            ? `${event.status} ${event.cwd ?? ''} ${event.ms ?? ''}`
                            : event.kind === 'table'
                              ? `${event.title ?? ''} ${event.columns.join(' ')}`
                              : event.kind === 'fileContent'
                                ? `${event.pathHint ?? ''} ${event.content.slice(0, 100)}`
                                : event.kind === 'metric'
                                  ? `${event.label} ${event.value}`
                                  : event.kind === 'text'
                                    ? event.text
                                    : '';
      return haystack.toLowerCase().includes(query.toLowerCase());
    });
  }, [smartEvents, filter, query]);

  const summary = useMemo(() => {
    let errors = 0;
    let execs = 0;
    let tools = 0;
    smartEvents.forEach((event) => {
      if (event.kind === 'error') errors += 1;
      if (event.kind === 'exec') execs += 1;
      if (event.kind === 'tool') tools += 1;
    });
    return { errors, execs, tools };
  }, [smartEvents]);

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

        <div className="px-4 pt-3 flex items-center gap-2">
          <div className="flex items-center gap-1 rounded-md border border-gray-700 bg-gray-800/80 p-1">
            <button
              onClick={() => allowRaw && setViewMode('raw')}
              disabled={!allowRaw}
              className={`px-2 py-1 text-xs rounded ${
                viewMode === 'raw' ? 'bg-blue-500/30 text-blue-200' : 'text-gray-400 hover:text-gray-200'
              } ${!allowRaw ? 'opacity-40 cursor-not-allowed' : ''}`}
            >
              Raw
            </button>
            <button
              onClick={() => allowSmart && setViewMode('smart')}
              disabled={!allowSmart}
              className={`px-2 py-1 text-xs rounded ${
                viewMode === 'smart' ? 'bg-blue-500/30 text-blue-200' : 'text-gray-400 hover:text-gray-200'
              } ${!allowSmart ? 'opacity-40 cursor-not-allowed' : ''}`}
            >
              Smart
            </button>
            <button
              onClick={() => allowJson && setViewMode('json')}
              disabled={!allowJson}
              className={`px-2 py-1 text-xs rounded ${
                viewMode === 'json' ? 'bg-blue-500/30 text-blue-200' : 'text-gray-400 hover:text-gray-200'
              } ${!allowJson ? 'opacity-40 cursor-not-allowed' : ''}`}
            >
              JSON
            </button>
          </div>
          {viewMode === 'smart' ? (
            <>
              <div className="ml-2 flex items-center gap-2 text-xs text-gray-400">
                <span className="flex items-center gap-1">
                  <AlertTriangle className="size-3 text-red-300" />
                  {summary.errors}
                </span>
                <span className="flex items-center gap-1">
                  <TerminalSquare className="size-3 text-blue-300" />
                  {summary.execs}
                </span>
                <span className="flex items-center gap-1">
                  <Wrench className="size-3 text-emerald-300" />
                  {summary.tools}
                </span>
              </div>
              <select
                className="ml-auto bg-gray-800 text-xs text-gray-300 border border-gray-700 rounded px-2 py-1"
                value={filter}
                onChange={(event) => setFilter(event.target.value as typeof filter)}
              >
                <option value="all">All</option>
                <option value="error">Errors</option>
                <option value="exec">Exec</option>
                <option value="tool">Tool</option>
              </select>
              <input
                className="bg-gray-800 text-xs text-gray-300 border border-gray-700 rounded px-2 py-1"
                placeholder="Search..."
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </>
          ) : null}
        </div>

        <div className="flex-1 overflow-auto p-4">
          {error ? (
            <div className="text-sm text-red-300">{error}</div>
          ) : viewMode === 'raw' ? (
            <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap">
              {loading ? '加载中...' : lines.join('\n') || '(空)'}
            </pre>
          ) : viewMode === 'json' ? (
            <div className="space-y-2">
              {loading ? (
                <div className="text-sm text-gray-300">Loading...</div>
              ) : jsonEvents.length === 0 ? (
                <div className="text-sm text-gray-400">(empty)</div>
              ) : (
                jsonEvents.map((event) => (
                  <pre key={event.id} className="text-xs text-gray-200 font-mono whitespace-pre-wrap">
                    {event.value ? JSON.stringify(event.value, null, 2) : event.raw}
                  </pre>
                ))
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {loading ? (
                <div className="text-sm text-gray-300">加载中...</div>
              ) : filteredEvents.length === 0 ? (
                <div className="text-sm text-gray-400">(空)</div>
              ) : (
                (() => {
                  const nodes: JSX.Element[] = [];
                  let currentRole: 'user' | 'thinking' | 'exec' | null = null;
                  for (let i = 0; i < filteredEvents.length; i += 1) {
                    const event = filteredEvents[i];
                    const next = filteredEvents[i + 1];
                    const roleBadge = currentRole ? <RoleBadge role={currentRole} /> : null;
                    if (event.kind === 'commandResult' && next?.kind === 'fileContent') {
                      nodes.push(
                        <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                          <div className="flex items-center gap-2">
                            {roleBadge}
                            <div className={`text-xs ${event.status === 'ok' ? 'text-emerald-300' : 'text-red-300'}`}>
                              {event.status === 'ok' ? 'Succeeded' : 'Failed'}
                            </div>
                          </div>
                          <div className="mt-1 text-xs text-gray-400">
                            {event.cwd ? `cwd: ${event.cwd} ` : ''}
                            {typeof event.ms === 'number' ? `? ${event.ms}ms ` : ''}
                            {typeof event.exitCode === 'number' ? `? exit ${event.exitCode}` : ''}
                          </div>
                          <div className="mt-2 text-xs text-gray-400">
                            File {next.pathHint || ''} {next.encodingWarning ? ' ? encoding warning' : ''}
                          </div>
                          <pre className="mt-2 text-xs text-gray-200 whitespace-pre-wrap">{next.content || '(empty)'}</pre>
                        </div>
                      );
                      i += 1;
                      continue;
                    }
                    if (event.kind === 'commandResult' && next?.kind === 'error') {
                      nodes.push(
                        <div key={event.id} className="rounded border border-red-500/40 bg-red-500/10 p-3">
                          <div className="flex items-center gap-2">
                            {roleBadge}
                            <div className="text-xs text-red-300">Failed</div>
                          </div>
                          <div className="mt-1 text-xs text-gray-400">
                            {event.cwd ? `cwd: ${event.cwd} ` : ''}
                            {typeof event.ms === 'number' ? `? ${event.ms}ms ` : ''}
                            {typeof event.exitCode === 'number' ? `? exit ${event.exitCode}` : ''}
                          </div>
                          <pre className="mt-2 text-xs text-red-100 whitespace-pre-wrap">{next.raw}</pre>
                        </div>
                      );
                      i += 1;
                      continue;
                    }
                    if (event.kind === 'section') {
                      nodes.push(
                        <details key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                          <summary className="cursor-pointer text-sm text-blue-200 flex items-center gap-2">
                            {roleBadge}
                            <span>{event.title}</span>
                          </summary>
                          <div className="mt-2 text-xs text-gray-200 whitespace-pre-wrap">{event.body || '(empty)'}</div>
                        </details>
                      );
                      continue;
                    }
                    if (event.kind === 'runStart') {
                      nodes.push(
                        <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                          <div className="flex items-center gap-2 text-xs text-gray-400">
                            {roleBadge}
                            <span>Run</span>
                          </div>
                          <div className="text-sm text-gray-200">OpenAI Codex v{event.version}</div>
                          <div className="mt-1 text-xs text-gray-400">{Object.entries(event.meta).map(([k, v]) => `${k}: ${v}`).join(' ? ')}</div>
                        </div>
                      );
                      continue;
                    }
                    if (event.kind === 'role') {
                      currentRole = event.role;
                      continue;
                    }
                    if (event.kind === 'json') {
                      if (isEmptyJson(event.value, event.raw)) {
                        continue;
                      }
                      const jsonBody = event.value != null ? JSON.stringify(event.value, null, 2) : event.raw;
                      nodes.push(
                        <details key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                          <summary className="cursor-pointer text-sm text-emerald-200 flex items-center gap-2">
                            {roleBadge}
                            <span>JSON</span>
                          </summary>
                          <pre className="mt-2 text-xs text-gray-200 whitespace-pre-wrap">{jsonBody}</pre>
                        </details>
                      );
                      continue;
                    }
                    if (event.kind === 'command') {
                      nodes.push(
                        <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                          <div className="flex items-center gap-2 text-xs text-gray-400">
                            {roleBadge}
                            <span>Exec</span>
                          </div>
                          <div className="text-sm text-gray-200 break-all">{event.cmd}</div>
                          <div className="mt-1 text-xs text-gray-400">{event.shell}</div>
                          {event.lifecycle === 'open' ? (
                            <div className="mt-1 text-xs text-blue-300">streaming...</div>
                          ) : null}
                        </div>
                      );
                      continue;
                    }
                    if (event.kind === 'commandResult') {
                      nodes.push(
                        <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                          <div className="flex items-center gap-2">
                            {roleBadge}
                            <div className={`text-xs ${event.status === 'ok' ? 'text-emerald-300' : 'text-red-300'}`}>
                              {event.status === 'ok' ? 'Succeeded' : 'Failed'}
                            </div>
                          </div>
                          <div className="mt-1 text-xs text-gray-400">
                            {event.cwd ? `cwd: ${event.cwd} ` : ''}
                            {typeof event.ms === 'number' ? `? ${event.ms}ms ` : ''}
                            {typeof event.exitCode === 'number' ? `? exit ${event.exitCode}` : ''}
                          </div>
                          {event.lifecycle === 'open' ? (
                            <div className="mt-1 text-xs text-blue-300">streaming...</div>
                          ) : null}
                        </div>
                      );
                      continue;
                    }
                    if (event.kind === 'exec') {
                      nodes.push(
                        <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                          <div className="flex items-center gap-2 text-xs text-gray-400">
                            {roleBadge}
                            <span>Exec</span>
                          </div>
                          <div className="text-sm text-gray-200 break-all">{event.cmd}</div>
                          <div className="mt-1 text-xs text-gray-400">
                            {event.cwd ? `cwd: ${event.cwd} ` : ''}
                            {typeof event.ms === 'number' ? `? ${event.ms}ms ` : ''}
                            {typeof event.exitCode === 'number' ? `? exit ${event.exitCode}` : ''}
                          </div>
                        </div>
                      );
                      continue;
                    }
                    if (event.kind === 'tool') {
                      nodes.push(
                        <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                          <div className="flex items-center gap-2 text-xs text-gray-400">
                            {roleBadge}
                            <span>Tool</span>
                          </div>
                          <div className="text-sm text-gray-200">{event.tool} ? {event.phase}</div>
                          {event.message ? <div className="mt-1 text-xs text-gray-300">{event.message}</div> : null}
                        </div>
                      );
                      continue;
                    }
                    if (event.kind === 'table') {
                      nodes.push(
                        <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                          <div className="flex items-center gap-2 text-xs text-gray-400">
                            {roleBadge}
                            <span>Directory</span>
                          </div>
                          <div className="text-xs text-gray-400">{event.title || ''}</div>
                          <div className="mt-2 overflow-auto">
                            <table className="w-full text-xs text-gray-200">
                              <thead>
                                <tr>
                                  {event.columns.map((c, ci) => (
                                    <th key={ci} className="text-left font-medium pr-4">{c}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {event.rows.map((r, ri) => (
                                  <tr key={ri}>
                                    {r.map((cell, ci) => (
                                      <td key={ci} className="pr-4 py-0.5">{cell}</td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      );
                      continue;
                    }
                    if (event.kind === 'fileContent') {
                      const markupKind = detectMarkupKind(event.content, event.pathHint);
                      if (markupKind) {
                        nodes.push(
                          <MarkupCard
                            key={event.id}
                            title={`File ${event.pathHint || ''}`}
                            source={event.content}
                            kind={markupKind}
                            badge={roleBadge}
                            meta={event.encodingWarning ? 'encoding warning' : undefined}
                          />
                        );
                        continue;
                      }
                      nodes.push(
                        <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                          <div className="flex items-center gap-2 text-xs text-gray-400">
                            {roleBadge}
                            <span>File {event.pathHint || ''} {event.encodingWarning ? ' ? encoding warning' : ''}</span>
                          </div>
                          {event.lifecycle === 'open' ? (
                            <div className="mt-1 text-xs text-blue-300">streaming...</div>
                          ) : null}
                          <pre className="mt-2 text-xs text-gray-200 whitespace-pre-wrap">{event.content || '(empty)'}</pre>
                        </div>
                      );
                      continue;
                    }
                    if (event.kind === 'metric') {
                      nodes.push(
                        <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                          <div className="flex items-center gap-2 text-xs text-gray-400">
                            {roleBadge}
                            <span>Metric</span>
                          </div>
                          <div className="text-sm text-gray-200">{event.label}: <span className="font-semibold text-emerald-200">{event.value}</span></div>
                        </div>
                      );
                      continue;
                    }
                    if (event.kind === 'thinking') {
                      nodes.push(
                        <details key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                          <summary className="cursor-pointer text-sm text-purple-200 flex items-center gap-2">
                            {roleBadge}
                            <span>Thinking</span>
                          </summary>
                          <div className="mt-2 text-xs text-gray-200">
                            <div className="font-semibold text-purple-100">{event.title}</div>
                            {event.body ? <div className="mt-2 whitespace-pre-wrap text-gray-200">{event.body}</div> : null}
                          </div>
                        </details>
                      );
                      continue;
                    }
                    if (event.kind === 'error') {
                      nodes.push(
                        <details key={event.id} className="rounded border border-red-500/40 bg-red-500/10 p-3">
                          <summary className="cursor-pointer text-sm text-red-200 flex items-center gap-2">
                            {roleBadge}
                            <span>{event.errorType}</span>
                          </summary>
                          <pre className="mt-2 text-xs text-red-100 whitespace-pre-wrap">{event.raw}</pre>
                        </details>
                      );
                      continue;
                    }
                    if (event.kind === 'text') {
                      const markupKind = detectMarkupKind(event.text);
                      if (markupKind) {
                        nodes.push(
                          <MarkupCard
                            key={event.id}
                            title="Markup"
                            source={event.text}
                            kind={markupKind}
                            badge={roleBadge}
                          />
                        );
                        continue;
                      }
                      nodes.push(
                        <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                          {roleBadge ? <div className="mb-1">{roleBadge}</div> : null}
                          <div className="text-xs text-gray-200 whitespace-pre-wrap">{event.text}</div>
                        </div>
                      );
                      continue;
                    }
                  }
                  return nodes;
                })()
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
