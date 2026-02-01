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
    iconBg: 'bg-blue-500/20',
    iconText: 'text-blue-400',
    nameText: 'text-blue-400',
    filterActive: 'bg-blue-500/20 text-blue-400',
  },
  Director: {
    icon: Bot,
    iconBg: 'bg-purple-500/20',
    iconText: 'text-purple-400',
    nameText: 'text-purple-400',
    filterActive: 'bg-purple-500/20 text-purple-400',
  },
  QA: {
    icon: CheckCircle,
    iconBg: 'bg-green-500/20',
    iconText: 'text-green-400',
    nameText: 'text-green-400',
    filterActive: 'bg-green-500/20 text-green-400',
  },
  Reviewer: {
    icon: Activity,
    iconBg: 'bg-orange-500/20',
    iconText: 'text-orange-400',
    nameText: 'text-orange-400',
    filterActive: 'bg-orange-500/20 text-orange-400',
  },
  System: {
    icon: MessageSquare,
    iconBg: 'bg-gray-500/20',
    iconText: 'text-gray-400',
    nameText: 'text-gray-400',
    filterActive: 'bg-gray-500/20 text-gray-400',
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
    <div className="h-full bg-[#1e1e1e] border-l border-gray-800 flex flex-col">
      <div className="px-4 py-3 border-b border-gray-800 bg-[#252526]">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <MessageSquare className="size-5 text-blue-400" />
            <h2 className="text-sm font-semibold text-gray-300">对话流</h2>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Activity className="size-3" />
            <span>{live ? '实时' : '离线'}</span>
            <div className="ml-2 flex items-center gap-1 rounded bg-gray-800 p-0.5">
              <button
                onClick={() => setViewMode('tasks')}
                className={`px-2 py-0.5 text-[11px] rounded ${viewMode === 'tasks' ? 'bg-blue-500/20 text-blue-300' : 'text-gray-400 hover:text-gray-200'
                  }`}
              >
                任务视图
              </button>
              <button
                onClick={() => setViewMode('stream')}
                className={`px-2 py-0.5 text-[11px] rounded ${viewMode === 'stream' ? 'bg-blue-500/20 text-blue-300' : 'text-gray-400 hover:text-gray-200'
                  }`}
              >
                日志流
              </button>
            </div>
          </div>
        </div>

        {viewMode === 'stream' ? (
          <div className="flex flex-wrap gap-1.5">
            <button
              onClick={() => setFilterSpeaker(null)}
              className={`px-2 py-1 text-xs rounded transition-colors ${!filterSpeaker
                  ? 'bg-blue-500/20 text-blue-400'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
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
                  className={`px-2 py-1 text-xs rounded transition-colors ${filterSpeaker === speaker
                      ? style.filterActive
                      : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                    }`}
                >
                  {speaker}
                </button>
              );
            })}
          </div>
        ) : null}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {loading ? (
          <DialoguePanelSkeleton />
        ) : viewMode === 'tasks' ? (
          taskGroups.length === 0 ? (
            <div className="text-xs text-gray-500">(暂无任务)</div>
          ) : (
            taskGroups.map((group) => {
              const isExpanded = expandedTasks[group.taskId] ?? (group.taskId === latestTaskId);
              const status = group.status || 'UNKNOWN';
              const statusTone =
                status === 'SUCCESS' || status === 'PASS'
                  ? 'bg-emerald-500/15 text-emerald-300'
                  : status === 'FAIL'
                    ? 'bg-red-500/15 text-red-300'
                    : status === 'BLOCKED'
                      ? 'bg-amber-500/15 text-amber-300'
                      : 'bg-gray-500/15 text-gray-300';
              const conflict = (status === 'SUCCESS' || status === 'PASS') && group.reviewerFindings.length > 0;
              const modifiedLabel = typeof group.modifiedCount === 'number' ? `${group.modifiedCount} files` : '-';
              const attemptLabel = group.attemptTotal
                ? `attempt ${group.attemptCurrent ?? group.attemptTotal}/${group.attemptTotal}`
                : '';
              const timeRange = group.startTs && group.endTs ? `${group.startTs} - ${group.endTs}` : group.endTs || '';

              return (
                <div key={group.taskId} className="rounded-xl border border-gray-800 bg-[#1a1f26] p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 text-xs text-gray-400">
                        <span className="rounded-full bg-gray-700/50 px-2 py-0.5 text-gray-300">
                          {group.taskId}
                        </span>
                        {attemptLabel ? (
                          <span className="rounded-full bg-gray-700/40 px-2 py-0.5 text-gray-300">{attemptLabel}</span>
                        ) : null}
                        {timeRange ? <span className="text-gray-500">{timeRange}</span> : null}
                      </div>
                      <div className="mt-1 text-sm font-semibold text-gray-200">
                        {group.title || (group.taskId === 'GLOBAL' ? '系统/未归类' : '任务进度')}
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-gray-400">
                        <span className={`rounded-full px-2 py-0.5 ${statusTone}`}>结果: {status}</span>
                        <span className="rounded-full bg-gray-700/40 px-2 py-0.5 text-gray-300">改动: {modifiedLabel}</span>
                        <span className="rounded-full bg-gray-700/40 px-2 py-0.5 text-gray-300">
                          风险: {group.reviewerFindings.length || 0}
                        </span>
                        {conflict ? (
                          <span className="flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-amber-300">
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
                      className="flex items-center gap-1 rounded px-2 py-1 text-[11px] text-gray-400 hover:bg-white/5"
                    >
                      {isExpanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
                      <span>{isExpanded ? '收起' : '展开'}</span>
                    </button>
                  </div>

                  {group.reviewerFindings.length > 0 ? (
                    <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                      <div className="mb-1 font-semibold">Reviewer 风险点</div>
                      <ul className="list-disc pl-4">
                        {group.reviewerFindings.slice(0, 4).map((item, idx) => (
                          <li key={`${group.taskId}-finding-${idx}`}>{item}</li>
                        ))}
                        {group.reviewerFindings.length > 4 ? <li>...</li> : null}
                      </ul>
                    </div>
                  ) : null}

                  {isExpanded ? (
                    <div className="mt-3 space-y-2">
                      {group.events.map((event, idx) => {
                        const style = speakerStyles[event.speaker] ?? speakerStyles.System;
                        const Icon = style.icon;
                        return (
                          <div
                            key={event.eventId || `${event.speaker}-${event.seq ?? idx}-${event.timestamp ?? ''}`}
                            className="flex gap-2 rounded-lg border border-gray-800 bg-gray-900/40 px-3 py-2"
                          >
                            <div
                              className={`flex-shrink-0 w-6 h-6 rounded-full ${style.iconBg} flex items-center justify-center`}
                            >
                              <Icon className={`size-3 ${style.iconText}`} />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2 text-[11px] text-gray-500">
                                <span className={style.nameText}>{event.speaker}</span>
                                <span>{event.type || 'log'}</span>
                                <span>{event.timestamp}</span>
                              </div>
                              <div className="text-xs text-gray-300 mt-1 whitespace-pre-wrap">{event.content}</div>
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
          <div className="text-xs text-gray-500">(暂无对话事件)</div>
        ) : (
          filteredEvents.map((event, index) => {
            const style = speakerStyles[event.speaker] ?? speakerStyles.System;
            const Icon = style.icon;

            return (
              <div
                key={event.eventId || `${event.speaker}-${event.seq ?? index}-${event.timestamp ?? ''}`}
                className="flex gap-3"
              >
                <div
                  className={`flex-shrink-0 w-8 h-8 rounded-full ${style.iconBg} flex items-center justify-center`}
                >
                  <Icon className={`size-4 ${style.iconText}`} />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-sm font-semibold ${style.nameText}`}>
                      {event.speaker}
                    </span>
                    <span className="text-xs text-gray-500">{event.timestamp}</span>
                    {event.refs?.task_id && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-gray-700 text-gray-400">
                        {event.refs.task_id}
                      </span>
                    )}
                    {event.refs?.phase && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-gray-700 text-gray-400">
                        {event.refs.phase}
                      </span>
                    )}
                  </div>

                  <div className="bg-gray-800/50 rounded-lg px-3 py-2 border border-gray-700">
                    <p className="text-sm text-gray-300 leading-relaxed">{event.content}</p>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="border-t border-gray-800 p-3 bg-[#252526]">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <div className="flex items-center gap-4">
            <span>总事件: {events.length}</span>
            <span>任务: {stats.totalTasks}</span>
            <span>完成数: {stats.completedTasks}</span>
          </div>
          <div className="flex items-center gap-1 text-green-400">
            <TrendingUp className="size-3" />
            <span>成功率: {stats.successRate}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
