import { useRef, useState, useEffect, useMemo } from 'react';
import { Panel, PanelGroup, PanelResizeHandle, ImperativePanelHandle } from 'react-resizable-panels';
import { apiFetch, connectWebSocket, openPath, pickWorkspace } from '@/api';
import { ControlPanel } from '@/app/components/ControlPanel';
import { ArtifactsSidebar } from '@/app/components/ArtifactsSidebar';
import { DialoguePanel, type DialogueEvent } from '@/app/components/DialoguePanel';
import { SnapshotPanel } from '@/app/components/SnapshotPanel';
import { StatusBar } from '@/app/components/StatusBar';
import { SettingsModal } from '@/app/components/SettingsModal';
import { MemoryPanel } from '@/app/components/MemoryPanel';
import { LogsModal } from '@/app/components/LogsModal';
import { MemoPanel, MemoItem } from '@/app/components/MemoPanel';
import { DocsInitDialog, type WorkspaceStatus } from '@/app/components/DocsInitDialog';
import { ProjectProgressPanel } from '@/app/components/ProjectProgressPanel';
import { CognitionPanel } from '@/app/components/CognitionPanel';
import { Toaster } from './components/ui/sonner';
import { toast } from 'sonner';
import { X } from 'lucide-react';
import { InterventionCenter } from '@/app/components/InterventionCenter';
import { RunHistoryModal } from '@/app/components/RunHistoryModal';
import { ErrorBoundaryClass } from '@/app/components/ErrorBoundary';
import { EnhancedNotificationManager } from '@/app/components/EnhancedNotificationManager';
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
  pm_model?: string;
  director_model?: string;
  model: string;
  prompt_profile: string;
  docs_init_model?: string;
  docs_init_provider?: string;
  docs_init_base_url?: string;
  docs_init_api_key?: string;
  docs_init_api_path?: string;
  docs_init_timeout?: number;
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
  pm_director_iterations?: number;
  pm_director_match_mode?: string;
  pm_max_failures?: number;
  pm_max_blocked?: number;
  pm_max_same?: number;
  director_iterations?: number;
  director_forever?: boolean;
  director_show_output?: boolean;
  qa_enabled?: boolean;
}

interface BackendStatus {
  running: boolean;
  pid: number | null;
  started_at: number | null;
  mode?: string;
  log_path?: string;
}

interface MemoListResponse {
  items: MemoItem[];
  count: number;
}

interface LanceDbStatus {
  ok: boolean;
  error?: string | null;
  python?: string | null;
  version?: string | null;
}

interface SnapshotPayload {
  timestamp: string;
  focus?: string;
  notes?: string;
  tasks?: unknown[];
  goals?: string[] | null;
  plan_text?: string | null;
  plan_mtime?: string | null;
  file_status?: string[];
  file_paths?: string[];
  pm_state?: Record<string, unknown>;
  director_state?: Record<string, unknown>;
  agents_review?: AgentsReviewInfo | null;
  runtime_issues?: RuntimeIssue[] | null;
  git?: {
    present?: boolean;
    root?: string;
  };
  workspace_status?: WorkspaceStatus | null;
  docs_present?: boolean;
}

interface AgentsReviewInfo {
  needs_review: boolean;
  has_agents: boolean;
  draft_path?: string | null;
  feedback_path?: string | null;
  draft_mtime?: string | null;
  feedback_mtime?: string | null;
  draft_failed?: boolean | null;
}

interface RuntimeIssue {
  code: string;
  title: string;
  detail: string;
}

interface FilePayload {
  content: string;
  mtime: string;
}

const LIVE_CHANNELS = [
  'status',
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
  dialogue: '.harborpilot/runtime/DIALOGUE.jsonl',
  pm_report: '.harborpilot/runtime/PM_REPORT.md',
  pm_log: '.harborpilot/runtime/PM_LOG.jsonl',
  pm_subprocess: '.harborpilot/runtime/PM_SUBPROCESS.log',
  director_console: '.harborpilot/runtime/DIRECTOR_SUBPROCESS.log',
  planner: '.harborpilot/runtime/PLANNER_RESPONSE.md',
  ollama: '.harborpilot/runtime/OLLAMA_RESPONSE.md',
  qa: '.harborpilot/runtime/QA_RESPONSE.md',
  runlog: '.harborpilot/runtime/RUNLOG.md',
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

function normalizeAgentsFeedback(content: string) {
  if (!content) return '';
  const lines = content.split('\n');
  if (lines[0]?.startsWith('## ')) {
    return lines.slice(1).join('\n').trimStart();
  }
  return content;
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
  const [showCognition, setShowCognition] = useState(true);
  const [isBrainOpen, setIsBrainOpen] = useState(false);
  const [notifications, setNotifications] = useState<Array<{
    id: string;
    type: 'success' | 'error' | 'warning' | 'info' | 'loading';
    title?: string;
    message: string;
    duration?: number;
    actions?: Array<{ label: string; onClick: () => void }>;
    progress?: boolean;
    persist?: boolean;
  }>>([]);
  const [selectedFile, setSelectedFile] = useState<{
    id: string;
    name: string;
    path: string;
  } | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isDocsInitOpen, setIsDocsInitOpen] = useState(false);
  const [isInterventionOpen, setIsInterventionOpen] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [settings, setSettings] = useState<BackendSettings | null>(null);
  const [pmStatus, setPmStatus] = useState<BackendStatus | null>(null);
  const [directorStatus, setDirectorStatus] = useState<BackendStatus | null>(null);
  const [lancedbStatus, setLancedbStatus] = useState<LanceDbStatus | null>(null);
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
  const [memoItems, setMemoItems] = useState<MemoItem[]>([]);
  const [memoSelected, setMemoSelected] = useState<MemoItem | null>(null);
  const [memoData, setMemoData] = useState<FilePayload>({ content: '', mtime: '' });
  const [memoLoading, setMemoLoading] = useState(false);
  const [memoError, setMemoError] = useState<string | null>(null);
  const [memoCollapsed, setMemoCollapsed] = useState(false);
  const lastMemoRefreshRef = useRef(0);
  const [memoryCollapsed, setMemoryCollapsed] = useState(false);
  const [agentsReview, setAgentsReview] = useState<AgentsReviewInfo | null>(null);
  const [agentsDraftContent, setAgentsDraftContent] = useState('');
  const [agentsDraftMtime, setAgentsDraftMtime] = useState('');
  const [agentsFeedback, setAgentsFeedback] = useState('');
  const [agentsFeedbackSavedAt, setAgentsFeedbackSavedAt] = useState('');
  const [agentsFeedbackDirty, setAgentsFeedbackDirty] = useState(false);
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [isAgentsDialogOpen, setIsAgentsDialogOpen] = useState(false);
  const [agentsApplying, setAgentsApplying] = useState(false);
  const [isStartingPM, setIsStartingPM] = useState(false);
  const [isStoppingPM, setIsStoppingPM] = useState(false);
  const [isStartingDirector, setIsStartingDirector] = useState(false);
  const [isStoppingDirector, setIsStoppingDirector] = useState(false);
  const [isStoppingOllama, setIsStoppingOllama] = useState(false);
  const [runtimeIssue, setRuntimeIssue] = useState<RuntimeIssue | null>(null);
  const [isRuntimeDialogOpen, setIsRuntimeDialogOpen] = useState(false);
  const [planIssue, setPlanIssue] = useState<{ detail: string } | null>(null);
  const [isPlanDialogOpen, setIsPlanDialogOpen] = useState(false);
  const [dialogueEvents, setDialogueEvents] = useState<DialogueEvent[]>([]);
  const [wsLive, setWsLive] = useState(false);
  const seenDialogueIds = useRef<Set<string>>(new Set());
  const agentsDialogHoldRef = useRef<string | null>(null);
  const selectedFileRef = useRef<{
    id: string;
    name: string;
    path: string;
  } | null>(null);
  const memoPanelRef = useRef<ImperativePanelHandle>(null);
  const memoryPanelRef = useRef<ImperativePanelHandle>(null);
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
  const [isLanceDbDialogOpen, setIsLanceDbDialogOpen] = useState(false);
  const [pmUserAction, setPmUserAction] = useState<'start' | 'stop' | 'once' | null>(null);
  const lastPmStopShownAtRef = useRef(0);
  const prevPmRunningRef = useRef<boolean | null>(null);
  const lancedbBlocked = lancedbStatus ? lancedbStatus.ok === false : true;
  const lancedbBlockMessage = useMemo(() => {
    if (!lancedbBlocked) return '';
    if (!lancedbStatus) {
      return 'Checking LanceDB status...';
    }
    const error = lancedbStatus?.error || 'lancedb not installed';
    const python = lancedbStatus?.python || 'unknown';
    return `LanceDB is required to run PM/Director.\n\nError: ${error}\nPython: ${python}`;
  }, [lancedbBlocked, lancedbStatus]);

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

  const refreshLanceDbStatus = async () => {
    try {
      const res = await apiFetch('/lancedb/status');
      if (!res.ok) {
        throw new Error('Failed to load LanceDB status');
      }
      const data = (await res.json()) as LanceDbStatus;
      setLancedbStatus(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'LanceDB unavailable';
      setLancedbStatus({ ok: false, error: message });
    }
  };

  const refreshSuccessStats = async () => {
    try {
      const res = await apiFetch('/files/read?path=.harborpilot/runtime/DIRECTOR_RESULT.json&tail_lines=200');
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
      const res = await apiFetch('/files/read?path=.harborpilot/runtime/memory/last_state.json&tail_lines=200');
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

  const refreshMemos = async () => {
    setMemoError(null);
    try {
      const res = await apiFetch('/memos/list?limit=200');
      if (!res.ok) {
        throw new Error('Failed to list memos');
      }
      const payload = (await res.json()) as MemoListResponse;
      const items = Array.isArray(payload.items) ? payload.items : [];
      setMemoItems(items);
      if (memoSelected) {
        const stillExists = items.find((item) => item.path === memoSelected.path);
        if (!stillExists) {
          setMemoSelected(items[0] || null);
        }
      } else if (items.length > 0) {
        setMemoSelected(items[0]);
      }
    } catch (err) {
      setMemoError(err instanceof Error ? err.message : 'Failed to list memos');
    }
  };

  const refreshMemoContent = async (item: MemoItem | null) => {
    if (!item) {
      setMemoData({ content: '', mtime: '' });
      setMemoError(null);
      return;
    }
    setMemoLoading(true);
    setMemoError(null);
    try {
      const res = await apiFetch(`/files/read?path=${encodeURIComponent(item.path)}`);
      if (!res.ok) {
        throw new Error('Failed to read memo');
      }
      const payload = (await res.json()) as FilePayload;
      setMemoData({ content: payload.content || '', mtime: payload.mtime || '' });
    } catch (err) {
      setMemoError(err instanceof Error ? err.message : 'Failed to read memo');
      setMemoData({ content: '', mtime: '' });
    } finally {
      setMemoLoading(false);
    }
  };

  const refreshAll = async () => {
    await Promise.all([
      refreshSettings(),
      refreshStatus(),
      refreshSnapshot(),
      refreshMemory(),
      refreshMemos(),
      refreshLanceDbStatus(),
      refreshSuccessStats(),
    ]);
  };

  useEffect(() => {
    refreshAll().catch((err) => {
      console.error('Failed to refresh all data:', err);
      toast.error('Failed to load initial data');
    });
  }, []);

  useEffect(() => {
    if (lancedbBlocked) {
      setIsLanceDbDialogOpen(true);
    } else {
      setIsLanceDbDialogOpen(false);
    }
  }, [lancedbBlocked]);

  useEffect(() => {
    const issue = snapshot?.runtime_issues?.[0] ?? null;
    setRuntimeIssue(issue);
    if (issue) {
      setIsRuntimeDialogOpen(true);
      setIsAgentsDialogOpen(false);
      setIsPlanDialogOpen(false);
    } else {
      setIsRuntimeDialogOpen(false);
    }
  }, [snapshot?.runtime_issues?.[0]?.code, snapshot?.runtime_issues?.[0]?.detail]);

  useEffect(() => {
    const review = snapshot?.agents_review ?? null;
    setAgentsReview(review);
    if (runtimeIssue) {
      return;
    }
    if (!review || !review.needs_review || !review.draft_path) {
      setIsAgentsDialogOpen(false);
      setAgentsDraftContent('');
      setAgentsDraftMtime('');
      setAgentsFeedbackSavedAt('');
      setAgentsFeedbackDirty(false);
      return;
    }
    const holdKey = agentsDialogHoldRef.current;
    if (review.draft_mtime && holdKey && review.draft_mtime === holdKey) {
      setIsAgentsDialogOpen(false);
      return;
    }
    setIsAgentsDialogOpen(true);
  }, [
    runtimeIssue,
    snapshot?.agents_review?.needs_review,
    snapshot?.agents_review?.draft_mtime,
    snapshot?.agents_review?.draft_path,
  ]);

  useEffect(() => {
    if (runtimeIssue || isAgentsDialogOpen) {
      setIsPlanDialogOpen(false);
      return;
    }
    const state = snapshot?.pm_state as Record<string, any> | undefined;
    const code = String(state?.last_director_error_code || '');
    if (code === 'PLAN_MISSING') {
      const detail = String(state?.last_director_error_detail || 'PLAN.md missing.');
      setPlanIssue({ detail });
      setIsPlanDialogOpen(true);
      return;
    }
    setIsPlanDialogOpen(false);
  }, [runtimeIssue, isAgentsDialogOpen, snapshot?.pm_state]);

  useEffect(() => {
    selectedFileRef.current = selectedFile;
  }, [selectedFile]);

  useEffect(() => {
    if (isAgentsDialogOpen) {
      loadAgentsReview().catch((err) => {
        console.error('Failed to load agents review:', err);
        toast.error('Failed to load AGENTS.md review');
      });
    }
  }, [
    isAgentsDialogOpen,
    agentsReview?.draft_path,
    agentsReview?.feedback_path,
    agentsReview?.draft_mtime,
  ]);

  useEffect(() => {
    if (settings && settings.auto_refresh === false) {
      return undefined;
    }
    const intervalMs = Math.max(1, settings?.refresh_interval ?? 3) * 1000;
    const timer = window.setInterval(() => {
      if (!wsLive) {
        refreshStatus().catch((err) => {
          console.error('Failed to refresh status:', err);
        });
        refreshSnapshot().catch((err) => {
          console.error('Failed to refresh snapshot:', err);
        });
        refreshLanceDbStatus().catch((err) => {
          console.error('Failed to refresh LanceDB status:', err);
        });
        refreshMemory().catch((err) => {
          console.error('Failed to refresh memory:', err);
        });
        refreshMemos().catch((err) => {
          console.error('Failed to refresh memos:', err);
        });
        refreshSuccessStats().catch((err) => {
          console.error('Failed to refresh success stats:', err);
        });
      }
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [settings?.refresh_interval, settings?.auto_refresh, wsLive]);

  useEffect(() => {
    if (!pmStatus) return;

    if (prevPmRunningRef.current === null) {
      prevPmRunningRef.current = pmStatus.running;
      if (pmStatus.running) {
        setPmUserAction(null);
      }
      return;
    }

    const wasRunning = prevPmRunningRef.current;
    prevPmRunningRef.current = pmStatus.running;

    if (pmStatus.running) {
      setPmUserAction(null);
      return;
    }

    if (!wasRunning) return;
    if (pmUserAction === 'stop') return;

    const wasOnce = pmUserAction === 'once' || (pmStatus.mode || '').toLowerCase() === 'once';
    if (wasOnce) return;

    showPmStoppedDialog().catch((err) => {
      console.error('Failed to show PM stopped dialog:', err);
    });
  }, [pmStatus, pmUserAction]);

  useEffect(() => {
    // Listen for custom event to open Intervention Hub
    const handleOpenIntervention = () => setIsInterventionOpen(true);
    window.addEventListener('open-intervention-center', handleOpenIntervention);

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
        connect(true);
        retryDelay = Math.min(retryDelay * 2, 10000);
      }, retryDelay);
    };

    const connect = async (forceRefresh = false) => {
      if (!active) return;
      try {
        socket = await connectWebSocket(forceRefresh);
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
        if (!active || !socket) return;
        setWsLive(true);
        socket.send(
          JSON.stringify({
            type: 'subscribe',
            channels: LIVE_CHANNELS,
            tail_lines: 200,
          })
        );
      };

      socket.onmessage = (event) => {
        if (!active) return;
        try {
          const payload = JSON.parse(event.data);
          const channel = String(payload.channel || '');
          if (payload.type === 'status') {
            if (payload.pm_status) {
              setPmStatus(payload.pm_status as BackendStatus);
            }
            if (payload.director_status) {
              setDirectorStatus(payload.director_status as BackendStatus);
            }
            if (payload.snapshot) {
              setSnapshot(payload.snapshot as SnapshotPayload);
            }
            if (payload.lancedb) {
              setLancedbStatus(payload.lancedb as LanceDbStatus);
            }
            if (payload.memory) {
              const memory = payload.memory as { content?: string; mtime?: string };
              setMemoryData({
                content: memory.content ?? '',
                mtime: memory.mtime ?? '',
              });
              setMemoryError(null);
            }
            if (payload.success_stats) {
              setSuccessStats(payload.success_stats as { successes?: number; total?: number; rate?: number });
            }
            return;
          }
          if (payload.type === 'snapshot' && Array.isArray(payload.lines)) {
            if (channel === 'dialogue') {
              const nextEvents: DialogueEvent[] = [];
              const newIds = new Set<string>();
              payload.lines.forEach((line: string) => {
                if (!line.trim()) return;
                try {
                  const raw = JSON.parse(line);
                  const normalized = normalizeDialogueEvent(raw);
                  if (!normalized) return;
                  const eventId = String(raw.event_id || '');
                  if (eventId) {
                    newIds.add(eventId);
                  }
                  nextEvents.push(normalized);
                } catch {
                  // ignore malformed line
                }
              });
              seenDialogueIds.current = newIds;
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
        if (!active) return;
        setWsLive(false);
        scheduleReconnect();
      };

      socket.onerror = () => {
        if (!active) return;
        setWsLive(false);
        scheduleReconnect();
      };
    };

    connect();

    return () => {
      active = false;
      cleanupTimer();
      socket?.close();
      window.removeEventListener('open-intervention-center', handleOpenIntervention);
    };
  }, [settings?.workspace]);

  useEffect(() => {
    if (wsLive || dialogueEvents.length > 0) return;
    apiFetch('/files/read?path=.harborpilot/runtime/DIALOGUE.jsonl&tail_lines=200')
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
      .catch((err) => {
        console.error('Failed to load dialogue events:', err);
      });
  }, [wsLive, settings?.workspace, dialogueEvents.length]);

  useEffect(() => {
    if (!selectedFile) {
      setFileData({ content: '', mtime: '' });
      setFileError(null);
      setFileBadge(null);
      return;
    }

    const controller = new AbortController();

    setFileLoading(true);
    setFileError(null);
    setFileBadge(null);
    apiFetch(`/files/read?path=${encodeURIComponent(selectedFile.path)}`)
      .then(async (res) => {
        if (controller.signal.aborted) return;
        if (!res.ok) {
          throw new Error('Failed to read file');
        }
        const payload = (await res.json()) as FilePayload;
        if (controller.signal.aborted) return;
        setFileData({ content: payload.content || '', mtime: payload.mtime || '' });
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        setFileError(err instanceof Error ? err.message : 'Failed to read file');
        setFileData({ content: '', mtime: '' });
      })
      .finally(() => {
        if (controller.signal.aborted) return;
        setFileLoading(false);
      });

    if (selectedFile.id === 'qa' || selectedFile.id === 'director-result') {
      apiFetch('/files/read?path=.harborpilot/runtime/DIRECTOR_RESULT.json&tail_lines=200')
        .then(async (res) => {
          if (controller.signal.aborted) return;
          if (!res.ok) return;
          const payload = (await res.json()) as FilePayload;
          if (controller.signal.aborted) return;
          if (!payload.content) return;
          let parsed: any = null;
          try {
            parsed = JSON.parse(payload.content);
          } catch {
            return;
          }
          const status = String(parsed?.status || '').trim().toUpperCase();
          const acceptance = parsed?.acceptance;
          if (controller.signal.aborted) return;
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
        .catch((err) => {
          console.error('Failed to load file test result:', err);
        });
    }

    return () => {
      controller.abort();
    };
  }, [selectedFile, settings?.workspace, settings?.ramdisk_root]);

  useEffect(() => {
    if (!settings?.show_memory) {
      setMemoryData({ content: '', mtime: '' });
      setMemoryError(null);
      return;
    }
    refreshMemory().catch((err) => {
      console.error('Failed to refresh memory:', err);
    });
  }, [settings?.show_memory, settings?.workspace, settings?.ramdisk_root]);

  useEffect(() => {
    refreshMemos().catch((err) => {
      console.error('Failed to refresh memos:', err);
    });
  }, [settings?.workspace, settings?.ramdisk_root]);

  useEffect(() => {
    refreshMemoContent(memoSelected).catch((err) => {
      console.error('Failed to refresh memo content:', err);
    });
  }, [memoSelected?.path, settings?.workspace, settings?.ramdisk_root]);

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

  const startPmLoop = async (resume = false) => {
    try {
      setPmActionError(null);
      setIsStartingPM(true);
      if (lancedbBlocked) {
        toast.warning(lancedbBlockMessage || 'LanceDB is required to start PM.');
        return;
      }
      setPmUserAction('start');
      const url = resume ? '/pm/start_loop?resume=true' : '/pm/start_loop';
      const res = await apiFetch(url, { method: 'POST' });
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
            const logPath = status.log_path || '.harborpilot/runtime/PM_SUBPROCESS.log';
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
        toast.error('Failed to start PM');
        throw new Error(combined);
      }
      refreshStatus();
    } catch (err) {
      console.error(err);
      const message = err instanceof Error ? err.message : 'PM action failed';
      openPmLogsWithBanner(message);
      toast.error(message);
    } finally {
      setIsStartingPM(false);
    }
  };

  const togglePm = async () => {
    try {
      setPmActionError(null);
      if (pmStatus?.running) {
        setIsStoppingPM(true);
        setPmUserAction('stop');
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
        refreshStatus();
      } else {
        await startPmLoop(false);
      }
    } catch (err) {
      console.error(err);
      const message = err instanceof Error ? err.message : 'PM action failed';
      openPmLogsWithBanner(message);
      toast.error(message);
    } finally {
      setIsStoppingPM(false);
    }
  };

  const runPmOnce = async () => {
    try {
      setPmActionError(null);
      if (lancedbBlocked) {
        toast.warning(lancedbBlockMessage || 'LanceDB is required to run PM.');
        return;
      }
      setIsStartingPM(true);
      setPmUserAction('once');
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
            const logPath = status.log_path || '.harborpilot/runtime/PM_SUBPROCESS.log';
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
        toast.error('Failed to run PM once');
        throw new Error(combined);
      }
      refreshStatus();
    } catch (err) {
      console.error(err);
      const message = err instanceof Error ? err.message : 'PM run-once failed';
      openPmLogsWithBanner(message);
      toast.error(message);
    } finally {
      setIsStartingPM(false);
    }
  };

  const toggleDirector = async () => {
    try {
      setDirectorActionError(null);
      if (directorStatus?.running) {
        setIsStoppingDirector(true);
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
        setIsStartingDirector(true);
        if (agentsRequired) {
          if (agentsDraftReady) {
            setIsAgentsDialogOpen(true);
            toast.warning('请先审阅并确认 AGENTS.generated.md，再启动 Director。');
          } else {
            toast.warning('请先运行 PM，让其读取 docs 并生成 AGENTS.generated.md。');
          }
          return;
        }
        if (lancedbBlocked) {
          toast.warning(lancedbBlockMessage || 'LanceDB is required to start Director.');
          return;
        }
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
              const logPath = status.log_path || '.harborpilot/runtime/DIRECTOR_SUBPROCESS.log';
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
          setErrorDialogContent(detail + '\n(查看日志获取详情)');
          setIsErrorDialogOpen(true);
          throw new Error(combined);
        }
      }
      refreshStatus();
    } catch (err) {
      console.error(err);
      const message = err instanceof Error ? err.message : 'Director action failed';
      setDirectorActionError(summarizeActionError(message));
      toast.error(message);
    } finally {
      setIsStartingDirector(false);
      setIsStoppingDirector(false);
    }
  };

  const showPmStoppedDialog = async () => {
    const now = Date.now();
    if (now - lastPmStopShownAtRef.current < 1500) return;
    lastPmStopShownAtRef.current = now;
    let reportTail = '';
    let logTail = '';
    try {
      const reportRes = await apiFetch('/files/read?path=.harborpilot/runtime/PM_REPORT.md&tail_lines=200');
      if (reportRes.ok) {
        const payload = (await reportRes.json()) as FilePayload;
        reportTail = payload.content || '';
      }
    } catch {
      // ignore
    }
    try {
      const logRes = await apiFetch('/files/read?path=.harborpilot/runtime/PM_SUBPROCESS.log&tail_lines=200');
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
      setIsStoppingOllama(true);
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
            toast.error(`Failed to stop models: ${names}`);
          }
        } else if (payload.stopped && payload.stopped.length > 0) {
          toast.success(`Stopped models: ${payload.stopped.join(', ')}`);
        } else {
          toast.info('No running models to stop');
        }
      } catch {
        // ignore parse errors
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to stop Ollama models';
      setOllamaActionError(summarizeActionError(message));
      toast.error(message);
    } finally {
      setIsStoppingOllama(false);
    }
  };

  const loadAgentsReview = async () => {
    if (!agentsReview || !agentsReview.needs_review) return;
    setAgentsLoading(true);
    try {
      if (agentsReview.draft_path) {
        const res = await apiFetch(`/files/read?path=${encodeURIComponent(agentsReview.draft_path)}&tail_lines=2000`);
        if (res.ok) {
          const payload = (await res.json()) as FilePayload;
          setAgentsDraftContent(payload.content || '');
          setAgentsDraftMtime(payload.mtime || '');
        }
      } else {
        setAgentsDraftContent('(draft missing)');
        setAgentsDraftMtime('');
      }
      if (agentsReview.feedback_path && !agentsFeedbackDirty) {
        const res = await apiFetch(`/files/read?path=${encodeURIComponent(agentsReview.feedback_path)}&tail_lines=2000`);
        if (res.ok) {
          const payload = (await res.json()) as FilePayload;
          setAgentsFeedback(normalizeAgentsFeedback(payload.content || ''));
          setAgentsFeedbackSavedAt(payload.mtime || '');
        }
      }
    } catch {
      // ignore
    } finally {
      setAgentsLoading(false);
    }
  };

  const saveAgentsFeedback = async () => {
    if (!agentsReview?.needs_review) return;
    try {
      const res = await apiFetch('/agents/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: agentsFeedback }),
      });
      if (!res.ok) {
        let detail = 'Failed to save feedback';
        try {
          const payload = (await res.json()) as { detail?: string };
          if (payload.detail) detail = payload.detail;
        } catch {
          // ignore
        }
        throw new Error(detail);
      }
      setAgentsFeedbackDirty(false);
      const payload = (await res.json()) as { mtime?: string; cleared?: boolean };
      if (payload?.cleared) {
        setAgentsFeedbackSavedAt('');
      } else if (payload?.mtime) {
        setAgentsFeedbackSavedAt(payload.mtime);
      }
      if (agentsReview?.draft_mtime) {
        agentsDialogHoldRef.current = agentsReview.draft_mtime;
      } else if (agentsDraftMtime) {
        agentsDialogHoldRef.current = agentsDraftMtime;
      }
      setIsAgentsDialogOpen(false);
      toast.info('反馈已提交，正在等待 PM 重新生成草稿...');
      refreshSnapshot().catch((err) => {
        console.error('Failed to refresh snapshot after feedback:', err);
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save feedback';
      setErrorDialogTitle('Feedback save failed');
      setErrorDialogContent(message);
      setIsErrorDialogOpen(true);
    }
  };

  const applyAgentsDraft = async () => {
    if (!agentsReview?.needs_review || agentsApplying) return;
    setAgentsApplying(true);
    try {
      const res = await apiFetch('/agents/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ draft_path: agentsReview.draft_path }),
      });
      if (!res.ok) {
        let detail = 'Failed to copy AGENTS.md';
        try {
          const payload = (await res.json()) as { detail?: string };
          if (payload.detail) detail = payload.detail;
        } catch {
          // ignore
        }
        throw new Error(detail);
      }
      setIsAgentsDialogOpen(false);
      agentsDialogHoldRef.current = null;
      setAgentsDraftContent('');
      setAgentsDraftMtime('');
      setAgentsFeedback('');
      setAgentsFeedbackDirty(false);
      refreshSnapshot().catch((err) => {
        console.error('Failed to refresh snapshot after applying agents draft:', err);
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to copy AGENTS.md';
      setErrorDialogTitle('AGENTS copy failed');
      setErrorDialogContent(message);
      setIsErrorDialogOpen(true);
    } finally {
      setAgentsApplying(false);
    }
  };

  const openAgentsDraft = () => {
    const draftPath = agentsReview?.draft_path;
    if (!draftPath) return;
    setSelectedFile({
      id: 'agents-draft',
      name: 'AGENTS.generated.md',
      path: draftPath,
    });
    setIsAgentsDialogOpen(false);
  };

  const openPlanFile = () => {
    setSelectedFile({
      id: 'plan',
      name: 'PLAN.md',
      path: '.harborpilot/runtime/PLAN.md',
    });
    setIsPlanDialogOpen(false);
  };

  const saveSettings = async (payload: {
    pm_backend?: string;
    pm_model?: string;
    director_model?: string;
    model?: string;
    prompt_profile?: string;
    docs_init_model?: string;
    docs_init_provider?: string;
    docs_init_base_url?: string;
    docs_init_api_key?: string;
    docs_init_api_path?: string;
    docs_init_timeout?: number;
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
    try {
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
      toast.success('Settings saved');
    } catch (err) {
      console.error(err);
      toast.error('Failed to save settings');
    }
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

  const workspaceStatus = useMemo(() => {
    return snapshot?.workspace_status ?? null;
  }, [snapshot]);

  const docsMissing = useMemo(() => {
    if (snapshot?.docs_present === false) return true;
    return workspaceStatus?.status === 'NEEDS_DOCS_INIT';
  }, [snapshot?.docs_present, workspaceStatus?.status]);

  const agentsRequired = useMemo(() => {
    return Boolean(snapshot?.agents_review?.needs_review);
  }, [snapshot?.agents_review?.needs_review]);
  const agentsDraftReady = useMemo(() => {
    return Boolean(snapshot?.agents_review?.draft_path);
  }, [snapshot?.agents_review?.draft_path]);
  const agentsDraftFailed = useMemo(() => {
    if (agentsReview?.draft_failed) return true;
    const lowered = (agentsDraftContent || '').toLowerCase();
    return lowered.includes('generation failed') || lowered.includes('failed to write last message file');
  }, [agentsDraftContent, agentsReview?.draft_failed]);

  const snapshotTasks = useMemo(() => {
    return Array.isArray(snapshot?.tasks) ? snapshot?.tasks : null;
  }, [snapshot]);

  const handleRefresh = () => {
    refreshAll().catch(() => undefined);
  };

  const addNotification = (notification: {
    type: 'success' | 'error' | 'warning' | 'info' | 'loading';
    title?: string;
    message: string;
    duration?: number;
    actions?: Array<{ label: string; onClick: () => void }>;
    progress?: boolean;
    persist?: boolean;
  }) => {
    const id = Date.now().toString() + Math.random().toString(36).substr(2, 9);
    setNotifications(prev => [...prev, { ...notification, id }]);
    return id;
  };

  const removeNotification = (id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  const handlePickWorkspace = async () => {
    try {
      const picked = await pickWorkspace(settings?.workspace);
      if (picked) {
        await handleWorkspaceCommit(picked);
        toast.success('Workspace updated');
      }
    } catch (err) {
      console.error(err);
      toast.error('Failed to pick workspace');
    }
  };

  const handleOpenWorkspace = async () => {
    const target = settings?.workspace;
    if (!target) return;
    try {
      const result = await openPath(target);
      if (!result.ok) {
        console.error(result.error || 'Failed to open workspace');
        toast.error('Failed to open workspace folder');
      }
    } catch (err) {
      console.error(err);
      toast.error('Failed to open workspace');
    }
  };

  return (
    <ErrorBoundaryClass onError={(error, errorInfo) => {
      console.error('Application error:', error, errorInfo);
      addNotification({
        type: 'error',
        title: '应用错误',
        message: error.message || '发生未知错误',
        duration: 10000,
        persist: true,
        actions: [
          {
            label: '查看详情',
            onClick: () => {
              setIsLogsOpen(true);
            }
          }
        ]
      });
    }}>
      <div className="size-full flex flex-col bg-bg text-text-main font-sans selection:bg-accent selection:text-bg overflow-hidden antialiased relative">
        <div className="cyberpunk-border" />
        {/* 增强通知管理器 */}
        <EnhancedNotificationManager
          notifications={notifications}
          onDismiss={removeNotification}
          maxVisible={5}
        />

        {/* 顶部控制面板 */}
        <ControlPanel
          workspace={settings?.workspace || ''}
          pmRunning={!!pmStatus?.running}
          directorRunning={!!directorStatus?.running}
          pmToggleDisabled={(lancedbBlocked || docsMissing) && !pmStatus?.running}
          directorToggleDisabled={((lancedbBlocked || docsMissing) && !directorStatus?.running) || (agentsRequired && !directorStatus?.running)}
          directorBlockedReason={
            docsMissing && !directorStatus?.running
              ? 'docs/ missing'
              : agentsRequired && !directorStatus?.running
                ? agentsDraftFailed
                  ? 'AGENTS 草稿生成失败'
                  : agentsDraftReady
                    ? '需要先确认 AGENTS.md'
                    : '请先运行 PM 生成 AGENTS 草稿'
                : undefined
          }
          runOnceDisabled={lancedbBlocked || docsMissing || !!pmStatus?.running}
          onOpenSettings={() => setIsSettingsOpen(true)}
          onWorkspaceCommit={handleWorkspaceCommit}
          onPickWorkspace={handlePickWorkspace}
          onTogglePm={togglePm}
          onRunPmOnce={runPmOnce}
          onResumePm={() => startPmLoop(true)}
          onToggleDirector={toggleDirector}
          onStopOllama={stopOllamaModels}
          onRefresh={handleRefresh}
          onOpenBrain={() => setIsBrainOpen(true)}
          agentsNeeded={agentsRequired}
          agentsDraftReady={agentsDraftReady}
          agentsDraftFailed={agentsDraftFailed}
          onOpenAgentsReview={() => setIsAgentsDialogOpen(true)}
          onGenerateAgentsDraft={() => {
            runPmOnce().catch(() => undefined);
          }}
          workspaceError={workspaceError}
          isStartingPM={isStartingPM}
          isStoppingPM={isStoppingPM}
          isStartingDirector={isStartingDirector}
          isStoppingDirector={isStoppingDirector}
          isStoppingOllama={isStoppingOllama}
        />

        <div className="z-40 border-b border-border shadow-sm bg-bg-panel">
          <StatusBar
            pmRunning={!!pmStatus?.running}
            directorRunning={!!directorStatus?.running}
            pmStartedAt={pmStatus?.started_at ?? null}
            directorStartedAt={directorStatus?.started_at ?? null}
            pmMode={pmStatus?.mode ?? null}
            failures={pmFailures}
            iteration={pmIteration}
            pmBackend={settings?.pm_backend || 'codex'}
            directorModel={settings?.director_model || settings?.model || ''}
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
            lancedbOk={lancedbStatus?.ok ?? null}
            lancedbError={lancedbStatus?.error ?? null}
          />
        </div>

        {docsMissing ? (
          <div className="mx-4 mb-3 rounded border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="font-semibold text-emerald-100">Docs initialization required</div>
                <div className="text-xs text-emerald-200/80">
                  {workspaceStatus?.reason || 'docs/ directory not found'}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsDocsInitOpen(true)}
                className="rounded bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-400"
              >
                Initialize docs
              </button>
            </div>
          </div>
        ) : null}

        {agentsReview?.needs_review ? (
          <div className="mx-4 mb-3 rounded border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="font-semibold text-amber-100">
                  {agentsDraftFailed
                    ? 'AGENTS draft failed'
                    : agentsDraftReady
                      ? 'AGENTS draft ready'
                      : 'AGENTS missing'}
                </div>
                <div className="text-xs text-amber-200/80">
                  {agentsDraftFailed
                    ? 'Check PM log and retry.'
                    : agentsDraftReady
                      ? 'Open draft and apply to AGENTS.md.'
                      : 'Run PM once to generate the draft.'}
                </div>
              </div>
              {agentsDraftReady || agentsDraftFailed ? (
                <button
                  type="button"
                  onClick={() => setIsAgentsDialogOpen(true)}
                  className="rounded bg-amber-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-400"
                >
                  Open AGENTS Review
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    runPmOnce().catch(() => undefined);
                  }}
                  className="rounded bg-blue-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-400"
                >
                  Generate AGENTS
                </button>
              )}
            </div>
          </div>
        ) : null}

        <SnapshotPanel
          timestamp={snapshot?.timestamp ?? null}
          focus={snapshot?.focus ?? null}
          notes={snapshot?.notes ?? null}
          tasks={snapshotTasks}
          fileStatus={snapshot?.file_status ?? null}
          filePaths={snapshot?.file_paths ?? null}
          directorState={snapshot?.director_state ?? null}
        />

        {/* Main Content Area: Mission Control Grid */}
        <PanelGroup direction="horizontal" autoSaveId="harborpilot-main-layout-v2" className="flex-1 flex overflow-hidden relative">
          {/* Left Sidebar: Artifacts */}
          <Panel defaultSize={20} minSize={15} maxSize={30} order={1} className="flex flex-col z-0">
            <div className="size-full border-r border-white/10 bg-bg-panel/30 backdrop-blur-md flex flex-col z-0">
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
                onOpenHistory={() => setIsHistoryOpen(true)}
                fileStatusLines={snapshot?.file_status ?? null}
              />
            </div>
          </Panel>

          <PanelResizeHandle className="w-1 bg-white/5 hover:bg-accent transition-colors z-10" />

          {/* Center: Workspace / Progress */}
          <Panel order={2} className="flex flex-col min-w-0 bg-transparent relative z-0">
            {/* Gradient overlay for depth */}
            <div className="absolute inset-x-0 top-0 h-4 bg-gradient-to-b from-bg-panel/30 to-transparent pointer-events-none z-10"></div>
            <ProjectProgressPanel
              tasks={(snapshotTasks as any[]) || []}
              pmState={snapshot?.pm_state ?? null}
              focus={snapshot?.focus ?? null}
              notes={snapshot?.notes ?? null}
              goals={snapshot?.goals ?? null}
              planText={snapshot?.plan_text ?? null}
              planMtime={snapshot?.plan_mtime ?? null}
              successStats={successStats}
              pmRunning={!!pmStatus?.running}
              className="flex-1 min-h-0"
            />
          </Panel>

          <PanelResizeHandle className="w-1 bg-white/5 hover:bg-accent transition-colors z-10" />

          {/* Right Sidebar: Dialogue & Memory */}
          <Panel defaultSize={30} minSize={20} maxSize={50} order={3} className="flex flex-col min-h-0 border-l border-white/10 bg-bg-panel/30 backdrop-blur-md z-0">
            <PanelGroup direction="vertical" autoSaveId="harborpilot-right-layout-v2">
              <Panel order={1} className="flex flex-col min-h-0">
                <DialoguePanel events={dialogueEvents} live={wsLive} loading={!wsLive && dialogueEvents.length === 0} />
              </Panel>

              <PanelResizeHandle className="h-1 bg-white/5 hover:bg-accent transition-colors z-10" />

              <Panel
                order={2}
                defaultSize={25}
                minSize={5}
                ref={memoPanelRef}
                className="flex flex-col min-h-0 border-t border-border"
              >
                <div className="size-full flex flex-col overflow-hidden">
                  <MemoPanel
                    items={memoItems}
                    selected={memoSelected}
                    content={memoData.content}
                    mtime={memoData.mtime}
                    loading={memoLoading}
                    error={memoError}
                    onSelect={(item) => setMemoSelected(item)}
                    collapsed={memoCollapsed}
                    onToggle={() => {
                      const collapsed = !memoCollapsed;
                      setMemoCollapsed(collapsed);
                      const p = memoPanelRef.current;
                      if (p) {
                        if (collapsed) p.resize(6);
                        else p.resize(25);
                      }
                    }}
                  />
                </div>
              </Panel>

              {settings?.show_memory ? (
                <>
                  <PanelResizeHandle className="h-1 bg-white/5 hover:bg-accent transition-colors z-10" />
                  <Panel
                    order={3}
                    defaultSize={25}
                    minSize={5}
                    ref={memoryPanelRef}
                    className="flex flex-col min-h-0 border-t border-border"
                  >
                    <div className="size-full flex flex-col overflow-hidden">
                      <div className="flex h-full flex-col">
                        <div className="flex-none border-b border-white/5 bg-[#252526] px-2 flex items-center justify-between">
                          <div className="flex bg-black/20 p-1 rounded-lg">
                            <button
                              onClick={() => setShowCognition(true)}
                              className={`px-3 py-1 text-xs rounded transition-all ${showCognition ? 'bg-purple-500/20 text-purple-300 shadow-sm' : 'text-gray-500 hover:text-gray-300'}`}
                            >
                              Cognition
                            </button>
                            <button
                              onClick={() => setShowCognition(false)}
                              className={`px-3 py-1 text-xs rounded transition-all ${!showCognition ? 'bg-blue-500/20 text-blue-300 shadow-sm' : 'text-gray-500 hover:text-gray-300'}`}
                            >
                              Raw Memory
                            </button>
                          </div>
                          <button
                            onClick={() => {
                              const collapsed = !memoryCollapsed;
                              setMemoryCollapsed(collapsed);
                              const p = memoryPanelRef.current;
                              if (p) {
                                if (collapsed) p.resize(6);
                                else p.resize(25);
                              }
                            }}
                            className="p-1 text-gray-400 hover:text-white transition-colors"
                          >
                            <div className={`transform transition-transform ${memoryCollapsed ? '-rotate-90' : 'rotate-0'}`}>
                              <svg
                                xmlns="http://www.w3.org/2000/svg"
                                width="16"
                                height="16"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                              >
                                <path d="m6 9 6 6 6-6" />
                              </svg>
                            </div>
                          </button>
                        </div>

                        <div className="flex-1 overflow-hidden relative">
                          {showCognition ? (
                            <CognitionPanel events={dialogueEvents} loading={!wsLive} />
                          ) : (
                            <MemoryPanel
                              content={memoryData.content}
                              mtime={memoryData.mtime}
                              loading={memoryLoading}
                              error={memoryError}
                              collapsed={memoryCollapsed}
                              onToggle={() => { }}
                            />
                          )}
                        </div>
                      </div>
                    </div>
                  </Panel>
                </>
              ) : null}
            </PanelGroup>
          </Panel>
        </PanelGroup>

        {/* 底部状态栏 */}


        {/* 设置弹窗 */}
        <SettingsModal
          isOpen={isSettingsOpen}
          onClose={() => setIsSettingsOpen(false)}
          settings={settings}
          onSave={saveSettings}
        />

        <DocsInitDialog
          open={isDocsInitOpen}
          onOpenChange={setIsDocsInitOpen}
          workspace={settings?.workspace}
          workspaceStatus={workspaceStatus}
          docsPresent={snapshot?.docs_present}
          onApplied={() => {
            refreshSnapshot().catch(() => undefined);
            refreshSettings().catch(() => undefined);
          }}
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
        <AlertDialog
          open={isAgentsDialogOpen}
          onOpenChange={(open) => {
            if (open) {
              setIsAgentsDialogOpen(true);
            } else {
              setIsAgentsDialogOpen(false);
            }
          }}
        >
          <AlertDialogContent className="border border-emerald-500/30 bg-[#1f2125] max-w-3xl">
            <AlertDialogHeader>
              <AlertDialogTitle className="text-emerald-200">
                {agentsDraftFailed ? 'AGENTS.md 草稿生成失败' : 'AGENTS.md 草稿已生成'}
              </AlertDialogTitle>
              <AlertDialogDescription className="whitespace-pre-wrap text-gray-300">
                {agentsDraftFailed
                  ? '草稿生成失败（内容不完整或为空）。请先查看 PM 日志，修复后再重试生成。'
                  : '请审阅 AGENTS.md 草稿。如需修改，请填写反馈并提交，PM 将根据反馈重新生成草稿（窗口将暂时关闭）。'}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="rounded-md border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100">
              <div className="flex items-center justify-between gap-2">
                <span>草稿: {agentsReview?.draft_path || '.harborpilot/runtime/AGENTS.generated.md'}</span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setLogsSourceId('pm-subprocess');
                      setIsLogsOpen(true);
                    }}
                    className="rounded px-2 py-1 text-[11px] text-emerald-100 bg-emerald-500/20 hover:bg-emerald-500/30"
                  >
                    查看日志
                  </button>
                  <button
                    type="button"
                    onClick={openAgentsDraft}
                    className="rounded px-2 py-1 text-[11px] text-emerald-100 bg-emerald-500/20 hover:bg-emerald-500/30"
                  >
                    打开草稿
                  </button>
                </div>
              </div>
              <div>
                目标: {settings?.workspace ? `${settings.workspace}\\AGENTS.md` : 'workspace/AGENTS.md'}
              </div>
              {agentsDraftMtime ? <div>更新时间: {agentsDraftMtime}</div> : null}
              {agentsFeedbackSavedAt ? <div>反馈更新时间: {agentsFeedbackSavedAt}</div> : null}
            </div>
            <div className="grid gap-3">
              <div className="rounded-md border border-gray-700 bg-[#181a1f]">
                <div className="flex items-center justify-between border-b border-gray-800 px-3 py-2 text-xs text-gray-400">
                  <span>AGENTS.generated.md</span>
                  {agentsLoading ? <span>加载中...</span> : null}
                </div>
                <pre className="h-[60vh] overflow-auto whitespace-pre-wrap p-3 text-xs text-gray-200">
                  {agentsDraftContent || '(empty)'}
                </pre>
              </div>
              <div className="rounded-md border border-gray-700 bg-[#181a1f] p-3">
                <div className="text-xs text-gray-400">修改建议（可多次提交）</div>
                <textarea
                  className="mt-2 h-28 w-full resize-none rounded border border-gray-700 bg-[#0f1115] p-2 text-xs text-gray-200 outline-none focus:border-emerald-400"
                  placeholder="请描述你希望 AGENTS.md 如何调整，例如：增加编码规范、补充必读文档路径、明确UTF-8要求..."
                  value={agentsFeedback}
                  onChange={(event) => {
                    setAgentsFeedback(event.target.value);
                    setAgentsFeedbackDirty(true);
                  }}
                />
                <div className="mt-2 text-[11px] text-gray-500">
                  提交后窗口会自动关闭，待 PM 生成新草稿后会自动重新弹出。
                </div>
              </div>
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel onClick={() => setIsAgentsDialogOpen(false)}>稍后</AlertDialogCancel>
              {agentsDraftFailed ? (
                <AlertDialogAction
                  onClick={(event) => {
                    event.preventDefault();
                    runPmOnce().catch(() => undefined);
                  }}
                  className="bg-blue-500 text-white hover:bg-blue-400"
                >
                  重试生成
                </AlertDialogAction>
              ) : null}
              <AlertDialogAction
                onClick={(event) => {
                  event.preventDefault();
                  saveAgentsFeedback().catch(() => undefined);
                }}
                className="bg-blue-500 text-white hover:bg-blue-400"
              >
                提交反馈 (将重生成)
              </AlertDialogAction>
              <AlertDialogAction
                onClick={applyAgentsDraft}
                disabled={agentsApplying || agentsDraftFailed}
                className="bg-emerald-500 text-white hover:bg-emerald-400"
              >
                {agentsApplying ? '复制中...' : '确认复制'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        <Toaster />
        <AlertDialog
          open={isRuntimeDialogOpen}
          onOpenChange={(open) => {
            if (open) {
              setIsRuntimeDialogOpen(true);
            } else {
              setIsRuntimeDialogOpen(false);
            }
          }}
        >
          <AlertDialogContent className="border border-amber-500/30 bg-[#1f2125] max-w-lg">
            <AlertDialogHeader>
              <AlertDialogTitle className="text-amber-200">{runtimeIssue?.title || '运行环境缺失'}</AlertDialogTitle>
              <AlertDialogDescription className="whitespace-pre-wrap text-gray-300">
                {runtimeIssue?.detail || '运行环境缺失，需要人工接入处理。'}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="rounded-md border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
              <div>问题代码: {runtimeIssue?.code || 'RUNTIME_ISSUE'}</div>
              <div>建议：安装缺失依赖或在设置中切换 backend。</div>
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel onClick={() => setIsRuntimeDialogOpen(false)}>稍后</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => {
                  setIsRuntimeDialogOpen(false);
                  setIsSettingsOpen(true);
                }}
                className="bg-amber-500 text-white hover:bg-amber-400"
              >
                打开设置
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        <AlertDialog
          open={isPlanDialogOpen}
          onOpenChange={(open) => {
            if (open) {
              setIsPlanDialogOpen(true);
            } else {
              setIsPlanDialogOpen(false);
            }
          }}
        >
          <AlertDialogContent className="border border-blue-500/30 bg-[#1f2125] max-w-lg">
            <AlertDialogHeader>
              <AlertDialogTitle className="text-blue-200">PLAN.md 需要人工补充</AlertDialogTitle>
              <AlertDialogDescription className="whitespace-pre-wrap text-gray-300">
                {planIssue?.detail || '请先编辑 PLAN.md，然后再继续运行 Director。'}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="rounded-md border border-blue-500/20 bg-blue-500/10 px-3 py-2 text-xs text-blue-100">
              <div>路径: .harborpilot/runtime/PLAN.md</div>
              <div>建议：补充清晰的下一步计划/任务。</div>
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel onClick={() => setIsPlanDialogOpen(false)}>稍后</AlertDialogCancel>
              <AlertDialogAction
                onClick={openPlanFile}
                className="bg-blue-500 text-white hover:bg-blue-400"
              >
                打开 PLAN.md
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        <AlertDialog open={isLanceDbDialogOpen} onOpenChange={setIsLanceDbDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>LanceDB required</AlertDialogTitle>
              <AlertDialogDescription className="whitespace-pre-wrap break-words text-left">
                {lancedbBlockMessage || 'LanceDB is required to continue.'}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel onClick={() => setIsLanceDbDialogOpen(false)}>Close</AlertDialogCancel>
              <AlertDialogAction onClick={() => refreshLanceDbStatus().catch(() => undefined)}>
                Check again
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        <AlertDialog open={isErrorDialogOpen} onOpenChange={setIsErrorDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{errorDialogTitle || 'Action failed'}</AlertDialogTitle>
              <AlertDialogDescription className="whitespace-pre-wrap break-words text-left">
                {errorDialogContent}
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

      <LogsModal isOpen={showLogs} onClose={() => setShowLogs(false)} workspace={settings?.workspace} />

      <InterventionCenter
        isOpen={isInterventionOpen}
        onClose={() => setIsInterventionOpen(false)}
      />

      <RunHistoryModal
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
      />

      {isBrainOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-[100] animate-in fade-in duration-200">
          <div className="bg-bg-panel/95 border border-white/10 rounded-xl w-[90vw] h-[85vh] flex flex-col shadow-2xl shadow-purple-900/40 relative">
            <button
              onClick={() => setIsBrainOpen(false)}
              className="absolute top-4 right-4 z-10 p-2 text-white/50 hover:text-white rounded-full bg-black/20 hover:bg-black/40 transition-colors"
            >
              <X className="size-5" />
            </button>
            <div className="flex-1 overflow-hidden p-6 relative">
              <CognitionPanel events={dialogueEvents} loading={!wsLive} />
            </div>
          </div>
        </div>
      )}
    </ErrorBoundaryClass>
  );
}
