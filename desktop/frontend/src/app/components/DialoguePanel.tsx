import { Bot, User, CheckCircle, MessageSquare, Activity, TrendingUp } from 'lucide-react';
import { useMemo, useState } from 'react';

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

export function DialoguePanel({ events, live }: DialoguePanelProps) {
  const [filterSpeaker, setFilterSpeaker] = useState<string | null>(null);

  const filteredEvents = filterSpeaker
    ? events.filter((e) => e.speaker === filterSpeaker)
    : events;

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
    const successCount = Array.from(resultByTaskId.values()).filter((status) => status === 'SUCCESS')
      .length;
    const successRate = totalTasks > 0 ? Math.round((successCount / totalTasks) * 100) : 0;
    return { totalTasks, successRate };
  }, [events]);

  return (
    <div className="h-full bg-[#1e1e1e] border-l border-gray-800 flex flex-col">
      {/* 头部 */}
      <div className="px-4 py-3 border-b border-gray-800 bg-[#252526]">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <MessageSquare className="size-5 text-blue-400" />
            <h2 className="text-sm font-semibold text-gray-300">Dialogue 对话流</h2>
          </div>
          <div className="flex items-center gap-1 text-xs text-gray-500">
            <Activity className="size-3" />
            <span>{live ? '实时' : '离线'}</span>
          </div>
        </div>

        {/* 角色筛选 */}
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setFilterSpeaker(null)}
            className={`px-2 py-1 text-xs rounded transition-colors ${
              !filterSpeaker
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
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  filterSpeaker === speaker
                    ? style.filterActive
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {speaker}
              </button>
            );
          })}
        </div>
      </div>

      {/* 对话列表 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {filteredEvents.length === 0 ? (
          <div className="text-xs text-gray-500">(no dialogue events)</div>
        ) : null}
        {filteredEvents.map((event, index) => {
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
        })}
      </div>

      {/* 底部统计 */}
      <div className="border-t border-gray-800 p-3 bg-[#252526]">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <div className="flex items-center gap-4">
            <span>总事件: {events.length}</span>
            <span>任务: {stats.totalTasks}</span>
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
