import {
  Bot,
  User,
  CheckCircle,
  MessageSquare,
  Activity,
  TrendingUp,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { DialoguePanelSkeleton } from './DialoguePanelSkeleton';

export interface DialogueEvent {
  seq?: number;
  eventId?: string;
  speaker: 'PM' | 'Director' | 'QA' | 'Reviewer' | 'System';
  type?: string;
  content: string;
  timestamp?: string;
  refs?: {
    task_id?: string;
    phase?: string;
  };
}

interface DialoguePanelProps {
  events: DialogueEvent[];
  live: boolean;
  loading?: boolean;
}

const speakerStyles = {
  PM: {
    icon: User,
    iconBg: 'bg-gradient-to-br from-blue-500/20 to-cyan-500/20',
    iconText: 'text-cyan-400',
    nameText: 'text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400',
    filterActive: 'bg-blue-500/20 text-blue-300 shadow-[0_0_15px_rgba(59,130,246,0.4)]',
    border: 'border-blue-500/30'
  },
  Director: {
    icon: Bot,
    iconBg: 'bg-gradient-to-br from-purple-500/20 to-pink-500/20',
    iconText: 'text-purple-400',
    nameText: 'text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-400',
    filterActive: 'bg-purple-500/20 text-purple-300 shadow-[0_0_15px_rgba(168,85,247,0.4)]',
    border: 'border-purple-500/30'
  },
  QA: {
    icon: CheckCircle,
    iconBg: 'bg-gradient-to-br from-emerald-500/20 to-green-500/20',
    iconText: 'text-emerald-400',
    nameText: 'text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-green-400',
    filterActive: 'bg-emerald-500/20 text-emerald-300 shadow-[0_0_15px_rgba(16,185,129,0.4)]',
    border: 'border-emerald-500/30'
  },
  Reviewer: {
    icon: Activity,
    iconBg: 'bg-gradient-to-br from-orange-500/20 to-amber-500/20',
    iconText: 'text-orange-400',
    nameText: 'text-orange-400',
    filterActive: 'bg-orange-500/20 text-orange-300 shadow-[0_0_15px_rgba(249,115,22,0.4)]',
    border: 'border-orange-500/30'
  },
  System: {
    icon: MessageSquare,
    iconBg: 'bg-white/5',
    iconText: 'text-gray-400',
    nameText: 'text-gray-400',
    filterActive: 'bg-white/10 text-gray-300 shadow-[0_0_10px_rgba(255,255,255,0.1)]',
    border: 'border-white/10'
  },
};

export function DialoguePanel({ events, live, loading = false }: DialoguePanelProps) {
  const [filterSpeaker, setFilterSpeaker] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'tasks' | 'stream'>('tasks');
  const [expandedTasks, setExpandedTasks] = useState<Record<string, boolean>>({});

  const filteredEvents = filterSpeaker ? events.filter((e) => e.speaker === filterSpeaker) : events;

  const taskGroups = useMemo(() => {
    const groups = new Map<
      string,
      {
        taskId: string;
        title?: string;
        events: DialogueEvent[];
        status?: string;
        reviewerFindings: string[];
        modifiedCount?: number;
        attemptCurrent?: number;
        attemptTotal?: number;
        startTs?: string;
        endTs?: string;
        order: number;
      }
    >();

    const extractTitle = (content: string) => {
      const assignMatch = content.match(/Assigning task\s+\S+:\s*(.+)$/i);
      if (assignMatch?.[1]) return assignMatch[1].trim();
      const cnMatch = content.match(/任务《(.+?)》/);
      if (cnMatch?.[1]) return cnMatch[1].trim();
      return '';
    };

    const extractStatus = (content: string) => {
      const match = content.match(/(SUCCESS|PASS|FAILED|FAIL|BLOCKED|ERROR)/i);
      if (!match?.[1]) return '';
      const raw = match[1].toUpperCase();
      if (raw === 'FAILED') return 'FAIL';
      return raw;
    };

    const extractReviewerFindings = (content: string) => {
      const markerIdx = content.search(/Reviewer[:：]/);
      if (markerIdx === -1) return [];
      const slice = content.slice(markerIdx);
      const parts = slice
        .split(/-\s+/)
        .slice(1)
        .map((part) => part.trim())
        .filter(Boolean);
      if (parts.length > 0) return parts;
      const tail = slice.replace(/Reviewer[:：]/, '').trim();
      return tail ? [tail] : [];
    };

    const extractModifiedCount = (content: string) => {
      const match = content.match(/Modified\s+(\d+)\s+files?/i);
      if (match?.[1]) return Number(match[1]);
      const cn = content.match(/改动文件数[:：]\s*(\d+)/);
      if (cn?.[1]) return Number(cn[1]);
      return undefined;
    };

    const extractAttempt = (content: string) => {
      const match = content.match(/attempt\s+(\d+)\s*\/\s*(\d+)/i);
      if (!match?.[1] || !match?.[2]) return null;
      return { current: Number(match[1]), total: Number(match[2]) };
    };

    events.forEach((event, index) => {
      const taskId = event.refs?.task_id || 'GLOBAL';
      const existing = groups.get(taskId);
      const group =
        existing || {
          taskId,
          events: [],
          reviewerFindings: [],
          order: index,
        };

      group.events.push(event);
      group.startTs = group.startTs || event.timestamp;
      group.endTs = event.timestamp || group.endTs;

      if (!group.title) {
        const title = extractTitle(event.content);
        if (title) group.title = title;
      }
      const status = extractStatus(event.content);
      if (status) group.status = status;

      const findings = extractReviewerFindings(event.content);
      if (findings.length) group.reviewerFindings.push(...findings);

      const modified = extractModifiedCount(event.content);
      if (typeof modified === 'number') group.modifiedCount = modified;

      const attempt = extractAttempt(event.content);
      if (attempt) {
        group.attemptCurrent = attempt.current;
        group.attemptTotal = attempt.total;
      }

      if (!existing) groups.set(taskId, group);
    });

    return Array.from(groups.values()).sort((a, b) => a.order - b.order);
  }, [events]);

  const latestTaskId = taskGroups.length > 0 ? taskGroups[taskGroups.length - 1].taskId : '';

  const stats = useMemo(() => {
    const taskIds = new Set<string>();
    const resultByTaskId = new Map<string, string>();
    events.forEach((event) => {
      const taskId = event.refs?.task_id;
      if (taskId) {
        taskIds.add(taskId);
      }
      if (event.type === 'result' && taskId) {
        const match = event.content.match(/Result:\s*([A-Za-z]+)/);
        if (match?.[1]) {
          resultByTaskId.set(taskId, match[1].toUpperCase());
        }
      }
    });
    const totalTasks = taskIds.size;
    const completedTasks = resultByTaskId.size;
    const successCount = Array.from(resultByTaskId.values()).filter(
      (status) => status === 'SUCCESS' || status === 'PASS'
    ).length;
    const successRate = completedTasks > 0 ? Math.round((successCount / completedTasks) * 100) : 0;
    return { totalTasks, completedTasks, successRate };
  }, [events]);

  return (
    <div className="h-full flex flex-col glass border-l border-white/5 bg-transparent">
      <div className="px-4 py-3 border-b border-white/5 bg-transparent">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="size-8 rounded-lg bg-accent/10 flex items-center justify-center text-accent shadow-[0_0_10px_rgba(124,58,237,0.2)]">
              <MessageSquare className="size-4" />
            </div>
            <h2 className="text-sm font-heading font-semibold text-text-main">对话流</h2>
          </div>
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <Activity className={`size-3 ${live ? 'text-status-success animate-pulse' : 'text-text-dim'}`} />
            <span className={live ? 'text-status-success' : 'text-text-dim'}>{live ? '实时' : '离线'}</span>
            <div className="ml-2 flex items-center gap-1 rounded bg-black/20 p-0.5 border border-white/5">
              <button
                onClick={() => setViewMode('tasks')}
                className={`px-3 py-1 text-[10px] rounded transition-all ${viewMode === 'tasks'
                  ? 'bg-accent/20 text-accent font-semibold shadow-[0_0_5px_rgba(124,58,237,0.3)]'
                  : 'text-text-dim hover:text-text-main'
                  }`}
              >
                任务视图
              </button>
              <button
                onClick={() => setViewMode('stream')}
                className={`px-3 py-1 text-[10px] rounded transition-all ${viewMode === 'stream'
                  ? 'bg-accent/20 text-accent font-semibold shadow-[0_0_5px_rgba(124,58,237,0.3)]'
                  : 'text-text-dim hover:text-text-main'
                  }`}
              >
                日志流
              </button>
            </div>
          </div>
        </div>

        {viewMode === 'stream' ? (
          <div className="flex flex-wrap gap-1.5 pt-2">
            <button
              onClick={() => setFilterSpeaker(null)}
              className={`px-2 py-1 text-[10px] rounded-md border transition-all ${!filterSpeaker
                ? 'bg-accent/20 text-accent border-accent/30 shadow-[0_0_8px_rgba(124,58,237,0.2)]'
                : 'bg-white/5 text-text-dim border-transparent hover:bg-white/10'
                }`}
            >
              全部
            </button>
            {Object.keys(speakerStyles).map((speaker) => {
              const style = speakerStyles[speaker as keyof typeof speakerStyles];
              return (
                <button
                  key={speaker}
                  onClick={() => setFilterSpeaker(speaker === filterSpeaker ? null : speaker)}
                  className={`px-2 py-1 text-[10px] rounded-md border border-transparent transition-all ${filterSpeaker === speaker
                    ? style.filterActive
                    : 'bg-white/5 text-text-dim hover:bg-white/10'
                    }`}
                >
                  {speaker}
                </button>
              );
            })}
          </div>
        ) : null}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
        {loading ? (
          <DialoguePanelSkeleton />
        ) : viewMode === 'tasks' ? (
          taskGroups.length === 0 ? (
            <div className="text-xs text-text-dim flex flex-col items-center justify-center h-40 opacity-50">
              <MessageSquare className="size-8 mb-2 opacity-50" />
              <span>(暂无任务)</span>
            </div>
          ) : (
            taskGroups.map((group) => {
              const isExpanded = expandedTasks[group.taskId] ?? (group.taskId === latestTaskId);
              const status = group.status || 'UNKNOWN';
              const statusTone =
                status === 'SUCCESS' || status === 'PASS'
                  ? 'bg-status-success/10 text-status-success border-status-success/20'
                  : status === 'FAIL'
                    ? 'bg-status-error/10 text-status-error border-status-error/20'
                    : status === 'BLOCKED'
                      ? 'bg-status-warning/10 text-status-warning border-status-warning/20'
                      : 'bg-white/5 text-text-dim border-white/10';
              const conflict = (status === 'SUCCESS' || status === 'PASS') && group.reviewerFindings.length > 0;
              const modifiedLabel = typeof group.modifiedCount === 'number' ? `${group.modifiedCount} files` : '-';
              const attemptLabel = group.attemptTotal
                ? `attempt ${group.attemptCurrent ?? group.attemptTotal}/${group.attemptTotal}`
                : '';
              const timeRange = group.startTs && group.endTs ? `${group.startTs} - ${group.endTs}` : group.endTs || '';

              return (
                <div key={group.taskId} className="rounded-xl border border-white/5 bg-white/5 p-3 backdrop-blur-sm transition-all hover:bg-white/10 hover:border-white/10">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 text-[10px] text-text-muted font-mono">
                        <span className="rounded px-1.5 py-0.5 bg-white/5 border border-white/5">
                          {group.taskId}
                        </span>
                        {attemptLabel ? (
                          <span className="rounded px-1.5 py-0.5 bg-white/5 opacity-70">{attemptLabel}</span>
                        ) : null}
                        {timeRange ? <span className="text-text-dim opacity-50">{timeRange}</span> : null}
                      </div>
                      <div className="mt-1 text-sm font-semibold text-text-main">
                        {group.title || (group.taskId === 'GLOBAL' ? '系统/未归类' : '任务进度')}
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-[10px] text-text-muted">
                        <span className={`rounded-full px-2 py-0.5 border ${statusTone}`}>结果: {status}</span>
                        <span className="rounded-full bg-white/5 px-2 py-0.5 text-text-dim border border-white/5">改动: {modifiedLabel}</span>
                        <span className="rounded-full bg-white/5 px-2 py-0.5 text-text-dim border border-white/5">
                          风险: {group.reviewerFindings.length || 0}
                        </span>
                        {conflict ? (
                          <span className="flex items-center gap-1 rounded-full bg-status-warning/10 px-2 py-0.5 text-status-warning border border-status-warning/30">
                            <AlertTriangle className="size-3" /> 结论冲突
                          </span>
                        ) : null}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() =>
                        setExpandedTasks((prev) => ({
                          ...prev,
                          [group.taskId]: !isExpanded,
                        }))
                      }
                      className="flex items-center gap-1 rounded px-2 py-1 text-[10px] text-text-dim hover:text-text-main hover:bg-white/10 transition-colors"
                    >
                      {isExpanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
                      <span>{isExpanded ? '收起' : '展开'}</span>
                    </button>
                  </div>

                  {group.reviewerFindings.length > 0 ? (
                    <div className="mt-3 rounded-lg border border-status-warning/30 bg-status-warning/5 px-3 py-2 text-xs text-status-warning shadow-[0_0_10px_rgba(249,115,22,0.1)]">
                      <div className="mb-1 font-semibold flex items-center gap-2">
                        <AlertTriangle className="size-3" /> Reviewer 风险点
                      </div>
                      <ul className="list-disc pl-4 space-y-1 opacity-90">
                        {group.reviewerFindings.slice(0, 4).map((item, idx) => (
                          <li key={`${group.taskId}-finding-${idx}`}>{item}</li>
                        ))}
                        {group.reviewerFindings.length > 4 ? <li>...</li> : null}
                      </ul>
                    </div>
                  ) : null}

                  {isExpanded ? (
                    <div className="mt-3 space-y-2 relative">
                      <div className="absolute left-[11px] top-2 bottom-2 w-px bg-white/5"></div>
                      {group.events.map((event, idx) => {
                        const style = speakerStyles[event.speaker] ?? speakerStyles.System;
                        const Icon = style.icon;
                        return (
                          <div
                            key={event.eventId || `${event.speaker}-${event.seq ?? idx}-${event.timestamp ?? ''}`}
                            className="flex gap-3 relative z-10 pl-2 group/msg"
                          >
                            <div
                              className={`flex-shrink-0 w-6 h-6 rounded-full ${style.iconBg} flex items-center justify-center ring-2 ring-bg-panel transition-transform group-hover/msg:scale-110`}
                            >
                              <Icon className={`size-3 ${style.iconText}`} />
                            </div>
                            <div className="min-w-0 flex-1 bg-black/20 rounded-lg p-2 border border-white/5 hover:border-white/10 transition-colors">
                              <div className="flex items-center gap-2 text-[10px] text-text-dim font-mono mb-1">
                                <span className={`${style.nameText} font-bold`}>{event.speaker}</span>
                                <span className="opacity-50">{event.type || 'log'}</span>
                                <span className="opacity-50 ml-auto">{event.timestamp}</span>
                              </div>
                              <div className="text-xs text-text-main whitespace-pre-wrap break-all leading-relaxed opacity-90">{event.content}</div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : null}
                </div>
              );
            })
          )
        ) : filteredEvents.length === 0 ? (
          <div className="text-xs text-text-dim flex flex-col items-center justify-center h-40 opacity-50">
            <span>(暂无对话事件)</span>
          </div>
        ) : (
          filteredEvents.map((event, index) => {
            const style = speakerStyles[event.speaker] ?? speakerStyles.System;
            const Icon = style.icon;

            return (
              <div
                key={event.eventId || `${event.speaker}-${event.seq ?? index}-${event.timestamp ?? ''}`}
                className="flex gap-3 group/msg"
              >
                <div
                  className={`flex-shrink-0 w-8 h-8 rounded-full ${style.iconBg} flex items-center justify-center ring-2 ring-transparent group-hover/msg:ring-accent/20 transition-all shadow-lg`}
                >
                  <Icon className={`size-4 ${style.iconText}`} />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-sm font-semibold ${style.nameText}`}>
                      {event.speaker}
                    </span>
                    <span className="text-[10px] text-text-dim font-mono">{event.timestamp}</span>
                    {event.refs?.task_id && (
                      <span className="text-[10px] px-1.5 py-0 rounded bg-white/10 text-text-dim border border-white/5">
                        {event.refs.task_id}
                      </span>
                    )}
                    {event.refs?.phase && (
                      <span className="text-[10px] px-1.5 py-0 rounded bg-white/10 text-text-dim border border-white/5">
                        {event.refs.phase}
                      </span>
                    )}
                  </div>

                  <div className="bg-white/5 rounded-2xl rounded-tl-sm px-4 py-3 border border-white/5 backdrop-blur-sm hover:bg-white/10 transition-colors shadow-sm">
                    <p className="text-sm text-text-main leading-relaxed break-all whitespace-pre-wrap">{event.content}</p>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="border-t border-white/5 p-3 bg-black/20 backdrop-blur-md">
        <div className="flex items-center justify-between text-[10px] text-text-dim font-mono">
          <div className="flex items-center gap-4">
            <span>总事件: {events.length}</span>
            <span>任务: {stats.totalTasks}</span>
            <span>完成数: {stats.completedTasks}</span>
          </div>
          <div className="flex items-center gap-1 text-emerald-400">
            <TrendingUp className="size-3" />
            <span>成功率: {stats.successRate}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
