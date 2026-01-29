import { useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch, connectWebSocket, openPath, pickWorkspace } from '@/api';
import { ControlPanel } from '@/app/components/ControlPanel';
import { ArtifactsSidebar } from '@/app/components/ArtifactsSidebar';
import { FileViewer } from '@/app/components/FileViewer';
import { DialoguePanel, type DialogueEvent } from '@/app/components/DialoguePanel';
import { SnapshotPanel } from '@/app/components/SnapshotPanel';
import { StatusBar } from '@/app/components/StatusBar';
import { SettingsModal } from '@/app/components/SettingsModal';
import { MemoryPanel } from '@/app/components/MemoryPanel';
import { LogsModal } from '@/app/components/LogsModal';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogAction,
  AlertDialogCancel,
} from '@/app/components/ui/alert-dialog';

interface BackendSettings {
  workspace: string;
  pm_backend: string;
  model: string;
  prompt_profile: string;
  interval: number;
  timeout: number;
  refresh_interval: number;
  auto_refresh: boolean;
  show_memory: boolean;
  ramdisk_root?: string;
  json_log_path?: string;
  pm_show_output?: boolean;
  pm_runs_director?: boolean;
  pm_director_show_output?: boolean;
  pm_director_timeout?: number;
  pm_max_failures?: number;
  pm_max_blocked?: number;
  pm_max_same?: number;
  director_iterations?: number;
  director_forever?: boolean;
  director_show_output?: boolean;
}

interface BackendStatus {
  running: boolean;
  pid: number | null;
  started_at: number | null;
  mode?: string;
  log_path?: string;
}

interface SnapshotPayload {
  timestamp: string;
  focus?: string;
  notes?: string;
  tasks?: unknown[];
  file_status?: string[];
  file_paths?: string[];
  pm_state?: Record<string, unknown>;
  director_state?: Record<string, unknown>;
  git?: {
    present?: boolean;
    root?: string;
  };
}

interface FilePayload {
  content: string;
  mtime: string;
}

const LIVE_CHANNELS = [
  'dialogue',
  'pm_report',
  'pm_log',
  'pm_subprocess',
  'director_console',
  'planner',
  'ollama',
  'qa',
  'runlog',
] as const;

const CHANNEL_TO_PATH: Record<string, string> = {
  dialogue: 'state/ollama/DIALOGUE.jsonl',
  pm_report: 'state/ollama/PM_REPORT.md',
  pm_log: 'state/ollama/PM_LOG.jsonl',
  pm_subprocess: 'state/ollama/PM_SUBPROCESS.log',
  director_console: 'state/ollama/DIRECTOR_SUBPROCESS.log',
  planner: 'state/ollama/PLANNER_RESPONSE.md',
  ollama: 'state/ollama/OLLAMA_RESPONSE.md',
  qa: 'state/ollama/QA_RESPONSE.md',
  runlog: 'state/ollama/RUNLOG.md',
};

function appendLiveContent(prev: string, incoming: string, maxLines = 2000) {
  const combined = prev ? `${prev}\n${incoming}` : incoming;
  const lines = combined.split('\n');
  if (lines.length <= maxLines) {
    return combined;
  }
  return lines.slice(-maxLines).join('\n');
}

function normalizeDialogueEvent(raw: Record<string, any>): DialogueEvent | null {
  if (!raw) return null;
  const eventId = String(raw.event_id || '').trim();
  const rawSpeaker = String(raw.speaker || 'System');
  const speaker = ['PM', 'Director', 'QA', 'Reviewer', 'System'].includes(rawSpeaker)
    ? (rawSpeaker as DialogueEvent['speaker'])
    : 'System';
  const content = String(raw.text || raw.summary || raw.content || '').trim();
  let timestamp = String(raw.timestamp || raw.ts || raw.time || '').trim();
  if (timestamp.includes('T')) {
    timestamp = timestamp.split('T')[1].replace('Z', '');
  }
  return {
    seq: raw.seq,
    eventId: eventId || undefined,
    speaker,
    type: raw.type,
    content: content || '(empty)',
    timestamp,
    refs: raw.refs,
  };
}

function summarizeActionError(detail: string, maxLen = 160) {
  const trimmed = detail.trim();
  if (!trimmed) return 'Action failed';
  const firstLine = trimmed.split('\n').find((line) => line.trim()) || trimmed;
  let summary = firstLine;
  if (summary.length > maxLen) {
    summary = summary.slice(0, Math.max(1, maxLen - 3)) + '...';
  }
  if (trimmed.includes('\n')) {
    summary += ' (see logs)';
  }
  return summary;
}

function trimLogPreview(text: string, maxLines = 20) {
  const lines = text.split('\n').filter((line) => line.trim().length > 0);
  if (lines.length <= maxLines) return lines.join('\n');
  return lines.slice(-maxLines).join('\n');
}

function extractPmStopSummary(reportText: string) {
  const lines = reportText
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
  if (!lines.length) return '';
  for (let idx = lines.length - 1; idx >= 0; idx -= 1) {
    const line = lines[idx];
    const lowered = line.toLowerCase();
    if (lowered.includes('halted') || lowered.startsWith('status:')) {
      return line;
    }
    if (lowered.startsWith('director exit')) {
      return line;
    }
  }
  const last = lines[lines.length - 1];
  if (last.startsWith('{') || last.startsWith('[')) {
    return '';
  }
  return last;
}

export default function App() {
  const [selectedFile, setSelectedFile] = useState<{
    id: string;
    name: string;
    path: string;
  } | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settings, setSettings] = useState<BackendSettings | null>(null);
  const [pmStatus, setPmStatus] = useState<BackendStatus | null>(null);
  const [directorStatus, setDirectorStatus] = useState<BackendStatus | null>(null);
  const [snapshot, setSnapshot] = useState<SnapshotPayload | null>(null);
  const [fileData, setFileData] = useState<FilePayload>({ content: '', mtime: '' });
  const [fileLoading, setFileLoading] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const [fileBadge, setFileBadge] = useState<{ text: string; tone: 'green' | 'yellow' | 'red' } | null>(
    null
  );
  const [memoryData, setMemoryData] = useState<FilePayload>({ content: '', mtime: '' });
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [memoryError, setMemoryError] = useState<string | null>(null);
  const [dialogueEvents, setDialogueEvents] = useState<DialogueEvent[]>([]);
  const [wsLive, setWsLive] = useState(false);
  const seenDialogueIds = useRef<Set<string>>(new Set());
  const selectedFileRef = useRef<{
    id: string;
    name: string;
    path: string;
  } | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [isLogsOpen, setIsLogsOpen] = useState(false);
  const [logsSourceId, setLogsSourceId] = useState<string | null>(null);
  const [logsBanner, setLogsBanner] = useState<string | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [pmActionError, setPmActionError] = useState<string | null>(null);
  const [directorActionError, setDirectorActionError] = useState<string | null>(null);
  const [ollamaActionError, setOllamaActionError] = useState<string | null>(null);
  const [healthStatus, setHealthStatus] = useState<string | null>(null);
  const [successStats, setSuccessStats] = useState<{ successes?: number; total?: number; rate?: number }>({});
  const [isErrorDialogOpen, setIsErrorDialogOpen] = useState(false);
  const [errorDialogTitle, setErrorDialogTitle] = useState<string>('');
  const [errorDialogContent, setErrorDialogContent] = useState<string>('');
  const pmStopRequestedRef = useRef(false);
  const pmRunOnceRequestedRef = useRef(false);
  const lastPmRunningRef = useRef<boolean | null>(null);
  const lastPmModeRef = useRef<string | null>(null);
  const lastPmStopShownAtRef = useRef(0);

  const markBackendError = (err: unknown) => {
    if (err instanceof Error && err.message) {
      setBackendError(err.message);
      return;
    }
    setBackendError('Backend unavailable');
  };

  const openPmLogsWithBanner = (message: string) => {
    setPmActionError(summarizeActionError(message));
    setLogsBanner(message);
    setLogsSourceId('pm-subprocess');
    setIsLogsOpen(true);
  };

  const refreshSettings = async () => {
    try {
      const res = await apiFetch('/settings');
      if (!res.ok) {
        throw new Error('Failed to load settings');
      }
      const data = (await res.json()) as BackendSettings;
      setSettings(data);
      setBackendError(null);
    } catch (err) {
      markBackendError(err);
      throw err;
    }
  };

  const refreshStatus = async () => {
    try {
      const [pmRes, directorRes] = await Promise.all([
        apiFetch('/pm/status'),
        apiFetch('/director/status'),
      ]);
      let ok = true;
      if (pmRes.ok) {
        setPmStatus(await pmRes.json());
      } else {
        ok = false;
      }
      if (directorRes.ok) {
        setDirectorStatus(await directorRes.json());
      } else {
        ok = false;
      }
      if (ok) {
        setBackendError(null);
      } else {
        setBackendError('Failed to load status');
      }
    } catch (err) {
      markBackendError(err);
      throw err;
    }
  };

  const refreshSnapshot = async () => {
    try {
      const res = await apiFetch('/state/snapshot');
      if (!res.ok) {
        throw new Error('Failed to load snapshot');
      }
      const data = (await res.json()) as SnapshotPayload;
      setSnapshot(data);
      setBackendError(null);
    } catch (err) {
      markBackendError(err);
      throw err;
    }
  };

  const refreshSuccessStats = async () => {
    try {
      const res = await apiFetch('/files/read?path=state/ollama/DIRECTOR_RESULT.json&tail_lines=200');
      if (!res.ok) return;
      const payload = (await res.json()) as FilePayload;
      if (!payload.content) return;
      let parsed: any = null;
      try {
        parsed = JSON.parse(payload.content);
      } catch {
        return;
      }
      let successes = 0;
      let total = 0;
      let rate: number | undefined = undefined;
      if (typeof parsed.successes === 'number') successes = parsed.successes;
      if (typeof parsed.total === 'number') total = parsed.total;
      if (typeof parsed.success_rate === 'number') rate = parsed.success_rate;
      if (Array.isArray(parsed.results)) {
        total = parsed.results.length;
        successes = parsed.results.filter((r: any) => String(r?.status || '').toLowerCase() === 'success').length;
      }
      if (total > 0 && rate === undefined) {
        rate = successes / total;
      }
      setSuccessStats({ successes, total, rate });
    } catch {
      setSuccessStats({});
    }
  };

  const refreshMemory = async () => {
    if (!settings?.show_memory) {
      setMemoryData({ content: '', mtime: '' });
      setMemoryError(null);
      return;
    }
    setMemoryLoading(true);
    setMemoryError(null);
    try {
      const res = await apiFetch('/files/read?path=state/ollama/memory/last_state.json&tail_lines=200');
      if (!res.ok) {
        throw new Error('Failed to read memory');
      }
      const payload = (await res.json()) as FilePayload;
      setMemoryData({ content: payload.content || '', mtime: payload.mtime || '' });
    } catch (err) {
      setMemoryError(err instanceof Error ? err.message : 'Failed to read memory');
      setMemoryData({ content: '', mtime: '' });
    } finally {
      setMemoryLoading(false);
    }
  };

  const refreshAll = async () => {
    await Promise.all([refreshSettings(), refreshStatus(), refreshSnapshot(), refreshMemory()]);
  };

  useEffect(() => {
    refreshAll().catch(() => undefined);
  }, []);

  useEffect(() => {
    selectedFileRef.current = selectedFile;
  }, [selectedFile]);

  useEffect(() => {
    if (settings && settings.auto_refresh === false) {
      return undefined;
    }
    const intervalMs = Math.max(1, settings?.refresh_interval ?? 3) * 1000;
    const timer = window.setInterval(() => {
      refreshStatus().catch(() => undefined);
      refreshSnapshot().catch(() => undefined);
      refreshMemory().catch(() => undefined);
      refreshSuccessStats().catch(() => undefined);
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [settings?.refresh_interval, settings?.auto_refresh]);

  useEffect(() => {
    if (!pmStatus) return;
    const wasRunning = lastPmRunningRef.current;
    const wasMode = lastPmModeRef.current;
    lastPmRunningRef.current = pmStatus.running;
    lastPmModeRef.current = pmStatus.mode ?? null;
    if (wasRunning && !pmStatus.running) {
      const stoppedByUser = pmStopRequestedRef.current;
      const wasOnce = (wasMode || '').toLowerCase() === 'once' || pmRunOnceRequestedRef.current;
      pmStopRequestedRef.current = false;
      pmRunOnceRequestedRef.current = false;
      if (!stoppedByUser && !wasOnce) {
        showPmStoppedDialog().catch(() => undefined);
      }
    }
  }, [pmStatus]);

  useEffect(() => {
    let active = true;
    let socket: WebSocket | null = null;
    let retryDelay = 1000;
    let reconnectTimer: number | null = null;

    const cleanupTimer = () => {
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    const scheduleReconnect = () => {
      if (!active) return;
      cleanupTimer();
      reconnectTimer = window.setTimeout(() => {
        if (!active) return;
        connect();
        retryDelay = Math.min(retryDelay * 2, 10000);
      }, retryDelay);
    };

    const connect = async () => {
      try {
        socket = await connectWebSocket();
      } catch {
        if (active) {
          setWsLive(false);
          scheduleReconnect();
        }
        return;
      }

      if (!active || !socket) return;
      retryDelay = 1000;
      cleanupTimer();

      socket.onopen = () => {
        setWsLive(true);
        socket?.send(
          JSON.stringify({
            type: 'subscribe',
            channels: LIVE_CHANNELS,
            tail_lines: 200,
          })
        );
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const channel = String(payload.channel || '');
          if (payload.type === 'snapshot' && Array.isArray(payload.lines)) {
            if (channel === 'dialogue') {
              const nextEvents: DialogueEvent[] = [];
              seenDialogueIds.current.clear();
              payload.lines.forEach((line: string) => {
                if (!line.trim()) return;
                try {
                  const raw = JSON.parse(line);
                  const normalized = normalizeDialogueEvent(raw);
                  if (!normalized) return;
                  const eventId = String(raw.event_id || '');
                  if (eventId) {
                    seenDialogueIds.current.add(eventId);
                  }
                  nextEvents.push(normalized);
                } catch {
                  // ignore malformed line
                }
              });
              setDialogueEvents(nextEvents.slice(-500));
            } else {
              const selectedPath = selectedFileRef.current?.path || '';
              const channelPath = CHANNEL_TO_PATH[channel];
              if (channelPath && selectedPath === channelPath) {
                setFileData((prev) => ({
                  content: payload.lines.join('\n'),
                  mtime: prev.mtime || '',
                }));
              }
            }
            return;
          }
          if (payload.type === 'line' && payload.text) {
            if (channel === 'dialogue') {
              try {
                const raw = JSON.parse(payload.text);
                const normalized = normalizeDialogueEvent(raw);
                if (!normalized) return;
                const eventId = String(raw.event_id || '');
                if (eventId && seenDialogueIds.current.has(eventId)) {
                  return;
                }
                if (eventId) {
                  seenDialogueIds.current.add(eventId);
                }
                setDialogueEvents((prev) => [...prev, normalized].slice(-500));
              } catch {
                // ignore malformed line
              }
              return;
            }
            const selectedPath = selectedFileRef.current?.path || '';
            const channelPath = CHANNEL_TO_PATH[channel];
            if (channelPath && selectedPath === channelPath) {
              setFileData((prev) => ({
                content: appendLiveContent(prev.content, payload.text),
                mtime: prev.mtime || '',
              }));
            }
          }
        } catch {
        }
      };

      socket.onclose = () => {
        if (active) {
          setWsLive(false);
          scheduleReconnect();
        }
      };

      socket.onerror = () => {
        if (active) {
          setWsLive(false);
          scheduleReconnect();
        }
      };
    };

    connect();

    return () => {
      active = false;
      cleanupTimer();
      socket?.close();
    };
  }, [settings?.workspace]);

  useEffect(() => {
    if (wsLive || dialogueEvents.length > 0) return;
    apiFetch('/files/read?path=state/ollama/DIALOGUE.jsonl&tail_lines=200')
      .then(async (res) => {
        if (!res.ok) return;
        const payload = (await res.json()) as FilePayload;
        if (!payload.content) return;
        const lines = payload.content.split('\\n');
        const nextEvents: DialogueEvent[] = [];
        seenDialogueIds.current.clear();
        lines.forEach((line) => {
          if (!line.trim()) return;
          try {
            const raw = JSON.parse(line);
            const normalized = normalizeDialogueEvent(raw);
            if (!normalized) return;
            const eventId = String(raw.event_id || '');
            if (eventId) {
              seenDialogueIds.current.add(eventId);
            }
            nextEvents.push(normalized);
          } catch {
            // ignore malformed line
          }
        });
        setDialogueEvents(nextEvents.slice(-500));
      })
      .catch(() => undefined);
  }, [wsLive, settings?.workspace, dialogueEvents.length]);

  useEffect(() => {
    if (!selectedFile) {
      setFileData({ content: '', mtime: '' });
      setFileError(null);
      setFileBadge(null);
      return;
    }

    setFileLoading(true);
    setFileError(null);
    setFileBadge(null);
    apiFetch(`/files/read?path=${encodeURIComponent(selectedFile.path)}`)
      .then(async (res) => {
        if (!res.ok) {
          throw new Error('Failed to read file');
        }
        const payload = (await res.json()) as FilePayload;
        setFileData({ content: payload.content || '', mtime: payload.mtime || '' });
      })
      .catch((err) => {
        setFileError(err instanceof Error ? err.message : 'Failed to read file');
        setFileData({ content: '', mtime: '' });
      })
      .finally(() => {
        setFileLoading(false);
      });

    if (selectedFile.id === 'qa' || selectedFile.id === 'director-result') {
      apiFetch('/files/read?path=state/ollama/DIRECTOR_RESULT.json&tail_lines=200')
        .then(async (res) => {
          if (!res.ok) return;
          const payload = (await res.json()) as FilePayload;
          if (!payload.content) return;
          let parsed: any = null;
          try {
            parsed = JSON.parse(payload.content);
          } catch {
            return;
          }
          const status = String(parsed?.status || '').trim().toUpperCase();
          const acceptance = parsed?.acceptance;
          if (acceptance === true || status === 'SUCCESS') {
            setFileBadge({ text: '✓ PASSED', tone: 'green' });
            return;
          }
          if (acceptance === false || status === 'FAIL') {
            setFileBadge({ text: '✗ FAILED', tone: 'red' });
            return;
          }
          if (status) {
            setFileBadge({ text: status, tone: 'yellow' });
          }
        })
        .catch(() => undefined);
    }
  }, [selectedFile, settings?.workspace, settings?.ramdisk_root]);

  useEffect(() => {
    if (!settings?.show_memory) {
      setMemoryData({ content: '', mtime: '' });
      setMemoryError(null);
      return;
    }
    refreshMemory().catch(() => undefined);
  }, [settings?.show_memory, settings?.workspace, settings?.ramdisk_root]);

  const handleWorkspaceCommit = async (value: string) => {
    try {
      setWorkspaceError(null);
      const res = await apiFetch('/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace: value }),
      });
      if (!res.ok) {
        let detail = 'Failed to update workspace';
        try {
          const payload = (await res.json()) as { detail?: string };
          if (payload.detail) {
            detail = payload.detail;
          }
        } catch {
          // ignore parse errors
        }
        throw new Error(detail);
      }
      const data = (await res.json()) as BackendSettings;
      setSettings(data);
      setWorkspaceError(null);
      refreshSnapshot();
    } catch (err) {
      console.error(err);
      setWorkspaceError(err instanceof Error ? err.message : 'Workspace update failed');
    }
  };

  const togglePm = async () => {
    try {
      setPmActionError(null);
      if (pmStatus?.running) {
        pmStopRequestedRef.current = true;
        const res = await apiFetch('/pm/stop', { method: 'POST' });
        if (!res.ok) {
          let detail = 'Failed to stop PM';
          try {
            const payload = (await res.json()) as { detail?: string };
            if (payload.detail) detail = payload.detail;
          } catch {
            // ignore parse errors
          }
          console.error('PM stop failed:', detail);
          throw new Error(detail);
        }
      } else {
        pmRunOnceRequestedRef.current = false;
        pmStopRequestedRef.current = false;
        const res = await apiFetch('/pm/start_loop', { method: 'POST' });
        if (!res.ok) {
          let detail = 'Failed to start PM';
          try {
            const payload = (await res.json()) as { detail?: string };
            if (payload.detail) detail = payload.detail;
          } catch {
            // ignore parse errors
          }
          let combined = detail;
          console.error('PM start failed:', detail);
          try {
            const statusRes = await apiFetch('/pm/status');
            if (statusRes.ok) {
              const status = (await statusRes.json()) as BackendStatus;
              const logPath = status.log_path || 'state/ollama/PM_SUBPROCESS.log';
              const tailRes = await apiFetch(`/files/read?path=${encodeURIComponent(logPath)}&tail_lines=200`);
              if (tailRes.ok) {
                const tailPayload = (await tailRes.json()) as FilePayload;
                if (tailPayload.content) {
                  const tailText = tailPayload.content;
                  console.error('PM log tail:\n' + tailText);
                  const lines = tailText.split('\n');
                  const preview = lines.slice(-20).join('\n');
                  combined = `${detail}\n\n${preview}`;
                }
              }
            }
          } catch {
            // ignore
          }
          setLogsSourceId('pm-subprocess');
          setIsLogsOpen(true);
          openPmLogsWithBanner(combined);
          throw new Error(combined);
        }
      }
      refreshStatus();
    } catch (err) {
      console.error(err);
      pmStopRequestedRef.current = false;
      pmRunOnceRequestedRef.current = false;
      const message = err instanceof Error ? err.message : 'PM action failed';
      openPmLogsWithBanner(message);
    }
  };

  const runPmOnce = async () => {
    try {
      setPmActionError(null);
      pmRunOnceRequestedRef.current = true;
      pmStopRequestedRef.current = false;
      const res = await apiFetch('/pm/run_once', { method: 'POST' });
      if (!res.ok) {
        let detail = 'Failed to run PM once';
        try {
          const payload = (await res.json()) as { detail?: string };
          if (payload.detail) detail = payload.detail;
        } catch {
          // ignore parse errors
        }
        let combined = detail;
        console.error('PM run-once failed:', detail);
        try {
          const statusRes = await apiFetch('/pm/status');
          if (statusRes.ok) {
            const status = (await statusRes.json()) as BackendStatus;
            const logPath = status.log_path || 'state/ollama/PM_SUBPROCESS.log';
            const tailRes = await apiFetch(`/files/read?path=${encodeURIComponent(logPath)}&tail_lines=200`);
            if (tailRes.ok) {
              const tailPayload = (await tailRes.json()) as FilePayload;
              if (tailPayload.content) {
                const tailText = tailPayload.content;
                console.error('PM log tail:\n' + tailText);
                const lines = tailText.split('\n');
                const preview = lines.slice(-20).join('\n');
                combined = `${detail}\n\n${preview}`;
              }
            }
          }
        } catch {
          // ignore
        }
        setLogsSourceId('pm-subprocess');
        setIsLogsOpen(true);
        openPmLogsWithBanner(combined);
        throw new Error(combined);
      }
      refreshStatus();
    } catch (err) {
      console.error(err);
      pmRunOnceRequestedRef.current = false;
      const message = err instanceof Error ? err.message : 'PM action failed';
      openPmLogsWithBanner(message);
    }
  };

  const toggleDirector = async () => {
    try {
      setDirectorActionError(null);
      if (directorStatus?.running) {
        const res = await apiFetch('/director/stop', { method: 'POST' });
        if (!res.ok) {
          let detail = 'Failed to stop Director';
          try {
            const payload = (await res.json()) as { detail?: string };
            if (payload.detail) detail = payload.detail;
          } catch {
            // ignore parse errors
          }
          console.error('Director stop failed:', detail);
          throw new Error(detail);
        }
      } else {
        const res = await apiFetch('/director/start', { method: 'POST' });
        if (!res.ok) {
          let detail = 'Failed to start Director';
          try {
            const payload = (await res.json()) as { detail?: string };
            if (payload.detail) detail = payload.detail;
          } catch {
            // ignore parse errors
          }
          let combined = detail;
          console.error('Director start failed:', detail);
          try {
            const statusRes = await apiFetch('/director/status');
            if (statusRes.ok) {
              const status = (await statusRes.json()) as BackendStatus;
              const logPath = status.log_path || 'state/ollama/DIRECTOR_SUBPROCESS.log';
              const tailRes = await apiFetch(`/files/read?path=${encodeURIComponent(logPath)}&tail_lines=200`);
              if (tailRes.ok) {
                const tailPayload = (await tailRes.json()) as FilePayload;
                if (tailPayload.content) {
                  const tailText = tailPayload.content;
                  console.error('Director log tail:\n' + tailText);
                  const lines = tailText.split('\n');
                  const preview = lines.slice(-20).join('\n');
                  combined = `${detail}\n\n${preview}`;
                }
              }
            }
          } catch {
            // ignore
          }
          setLogsSourceId('director');
          setIsLogsOpen(true);
          setDirectorActionError(summarizeActionError(combined));
          setErrorDialogTitle('Director start failed');
          setErrorDialogContent(combined);
          setIsErrorDialogOpen(true);
          throw new Error(combined);
        }
      }
      refreshStatus();
    } catch (err) {
      console.error(err);
      const message = err instanceof Error ? err.message : 'Director action failed';
      setDirectorActionError(summarizeActionError(message));
      setErrorDialogTitle('Director action failed');
      setErrorDialogContent(message);
      setIsErrorDialogOpen(true);
    }
  };

  const showPmStoppedDialog = async () => {
    const now = Date.now();
    if (now - lastPmStopShownAtRef.current < 1500) return;
    lastPmStopShownAtRef.current = now;
    let reportTail = '';
    let logTail = '';
    try {
      const reportRes = await apiFetch('/files/read?path=state/ollama/PM_REPORT.md&tail_lines=200');
      if (reportRes.ok) {
        const payload = (await reportRes.json()) as FilePayload;
        reportTail = payload.content || '';
      }
    } catch {
      // ignore
    }
    try {
      const logRes = await apiFetch('/files/read?path=state/ollama/PM_SUBPROCESS.log&tail_lines=200');
      if (logRes.ok) {
        const payload = (await logRes.json()) as FilePayload;
        logTail = payload.content || '';
      }
    } catch {
      // ignore
    }
    const summary = extractPmStopSummary(reportTail);
    const preview = trimLogPreview(logTail);
    let message = 'PM stopped unexpectedly.';
    if (summary) {
      message += `\n\nSummary: ${summary}`;
    }
    if (preview) {
      message += `\n\nLast log lines:\n${preview}`;
    }
    setPmActionError(summarizeActionError(message));
    setLogsBanner(message);
    setLogsSourceId('pm-subprocess');
    setIsLogsOpen(true);
  };

  const stopOllamaModels = async () => {
    try {
      setOllamaActionError(null);
      const res = await apiFetch('/ollama/stop', { method: 'POST' });
      if (!res.ok) {
        let detail = 'Failed to stop Ollama models';
        try {
          const payload = (await res.json()) as { detail?: string };
          if (payload.detail) detail = payload.detail;
        } catch {
          // ignore parse errors
        }
        throw new Error(detail);
      }
      try {
        const payload = (await res.json()) as { stopped?: string[]; failed?: Array<{ model: string }> };
        if (payload.failed && payload.failed.length > 0) {
          const names = payload.failed.map((item) => item.model).filter(Boolean).join(', ');
          if (names) {
            setOllamaActionError(summarizeActionError(`Failed to stop: ${names}`));
          }
        }
      } catch {
        // ignore parse errors
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to stop Ollama models';
      setOllamaActionError(summarizeActionError(message));
    }
  };

  const saveSettings = async (payload: {
    pm_backend?: string;
    model?: string;
    prompt_profile?: string;
    interval?: number;
    timeout?: number;
    refresh_interval?: number;
    auto_refresh?: boolean;
    show_memory?: boolean;
    ramdisk_root?: string;
    json_log_path?: string;
    pm_show_output?: boolean;
    pm_runs_director?: boolean;
    pm_director_show_output?: boolean;
    pm_director_timeout?: number;
    pm_max_failures?: number;
    pm_max_blocked?: number;
    pm_max_same?: number;
    director_iterations?: number;
    director_forever?: boolean;
    director_show_output?: boolean;
  }) => {
    const res = await apiFetch('/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error('Failed to save settings');
    }
    const data = (await res.json()) as BackendSettings;
    setSettings(data);
  };

  const pmIteration = useMemo(() => {
    const state = snapshot?.pm_state as Record<string, any> | undefined;
    if (!state) return null;
    return typeof state.pm_iteration === 'number' ? state.pm_iteration : null;
  }, [snapshot]);

  const pmFailures = useMemo(() => {
    const state = snapshot?.pm_state as Record<string, any> | undefined;
    if (!state) return null;
    return typeof state.consecutive_failures === 'number' ? state.consecutive_failures : null;
  }, [snapshot]);

  const gitPresent = useMemo(() => {
    return snapshot?.git?.present ?? null;
  }, [snapshot]);

  const snapshotTasks = useMemo(() => {
    return Array.isArray(snapshot?.tasks) ? snapshot?.tasks : null;
  }, [snapshot]);

  const handleRefresh = () => {
    refreshAll().catch(() => undefined);
  };

  const handlePickWorkspace = async () => {
    try {
      const picked = await pickWorkspace(settings?.workspace);
      if (picked) {
        await handleWorkspaceCommit(picked);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleOpenWorkspace = async () => {
    const target = settings?.workspace;
    if (!target) return;
    try {
      const result = await openPath(target);
      if (!result.ok) {
        console.error(result.error || 'Failed to open workspace');
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="size-full flex flex-col bg-[#1e1e1e] text-gray-200">
      {/* 顶部控制面板 */}
      <ControlPanel
        workspace={settings?.workspace || ''}
        pmRunning={!!pmStatus?.running}
        directorRunning={!!directorStatus?.running}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onWorkspaceCommit={handleWorkspaceCommit}
        onPickWorkspace={handlePickWorkspace}
        onTogglePm={togglePm}
        onRunPmOnce={runPmOnce}
        onToggleDirector={toggleDirector}
        onStopOllama={stopOllamaModels}
        onRefresh={handleRefresh}
        workspaceError={workspaceError}
      />

      <SnapshotPanel
        timestamp={snapshot?.timestamp ?? null}
        focus={snapshot?.focus ?? null}
        notes={snapshot?.notes ?? null}
        tasks={snapshotTasks}
        fileStatus={snapshot?.file_status ?? null}
        filePaths={snapshot?.file_paths ?? null}
        directorState={snapshot?.director_state ?? null}
      />

      {/* 主内容区 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左侧：运行产物导航 */}
        <div className="w-72 flex-shrink-0">
          <ArtifactsSidebar
            onFileSelect={(file) =>
              setSelectedFile({
                id: file.id,
                name: file.name,
                path: file.path,
              })
            }
            selectedFileId={selectedFile?.id || null}
            onOpenWorkspace={handleOpenWorkspace}
            fileStatusLines={snapshot?.file_status ?? null}
          />
        </div>

        {/* 中间：文件内容查看器 */}
        <div className="flex-1 min-w-0">
          <FileViewer
            selectedFile={selectedFile}
            content={fileData.content}
            mtime={fileData.mtime}
            loading={fileLoading}
            error={fileError}
            badge={fileBadge}
          />
        </div>

        {/* 右侧：Dialogue 对话流 */}
        <div className="w-96 flex-shrink-0 flex flex-col min-h-0">
          <div className="flex-1 min-h-0">
            <DialoguePanel events={dialogueEvents} live={wsLive} />
          </div>
          {settings?.show_memory ? (
            <div className="h-64 border-t border-gray-800">
              <MemoryPanel
                content={memoryData.content}
                mtime={memoryData.mtime}
                loading={memoryLoading}
                error={memoryError}
              />
            </div>
          ) : null}
        </div>
      </div>

      {/* 底部状态栏 */}
      <StatusBar
        pmRunning={!!pmStatus?.running}
        directorRunning={!!directorStatus?.running}
        pmStartedAt={pmStatus?.started_at ?? null}
        directorStartedAt={directorStatus?.started_at ?? null}
        pmMode={pmStatus?.mode ?? null}
        failures={pmFailures}
        iteration={pmIteration}
        pmBackend={settings?.pm_backend || 'codex'}
        directorModel={settings?.model || ''}
        backendError={backendError}
        onOpenLogs={() => {
          setLogsSourceId('pm-subprocess');
          setIsLogsOpen(true);
        }}
        gitPresent={gitPresent}
        pmError={pmActionError}
        directorError={directorActionError}
        ollamaError={ollamaActionError}
        successes={successStats.successes ?? null}
        total={successStats.total ?? null}
        rate={typeof successStats.rate === 'number' ? successStats.rate : null}
        onPingHealth={async () => {
          try {
            const res = await apiFetch('/health');
            if (!res.ok) {
              setHealthStatus('unhealthy');
              return;
            }
            const payload = await res.json();
            const ts = String(payload?.timestamp || '');
            setHealthStatus(ts || 'ok');
          } catch {
            setHealthStatus('unhealthy');
          }
        }}
        healthStatus={healthStatus}
      />

      {/* 设置弹窗 */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={settings}
        onSave={saveSettings}
      />

      <LogsModal
        isOpen={isLogsOpen}
        onClose={() => {
          setIsLogsOpen(false);
          setLogsBanner(null);
        }}
        initialSourceId={logsSourceId}
        banner={logsBanner}
        onDismissBanner={() => setLogsBanner(null)}
      />
      <AlertDialog open={isErrorDialogOpen} onOpenChange={setIsErrorDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{errorDialogTitle || 'Action failed'}</AlertDialogTitle>
            <AlertDialogDescription>
              <div className="whitespace-pre-wrap break-words text-left">{errorDialogContent}</div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setIsErrorDialogOpen(false)}>Close</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setIsErrorDialogOpen(false);
                setIsLogsOpen(true);
              }}
            >
              View logs
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
