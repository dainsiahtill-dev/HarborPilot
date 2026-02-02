import { Activity, AlertTriangle, ArrowRight, CheckCircle, Clock, ListChecks, Target } from 'lucide-react';
import type { PmTask, SuccessStats, PmState, TaskQueueItem, ProgressMode } from '../../types';
import {
  ProgressBar,
  CurrentTaskCard,
  TaskQueue,
  GoalsList,
  PlanPreview,
  TaskList,
} from './ProjectProgressPanel/index';


interface ProjectProgressPanelProps {
  tasks: PmTask[];
  pmState?: PmState | null;
  focus?: string | null;
  notes?: string | null;
  goals?: string[] | null;
  planText?: string | null;
  planMtime?: string | null;
  successStats?: SuccessStats | null;
  pmRunning?: boolean;
  className?: string;
}

const toText = (value: unknown): string => (typeof value === 'string' ? value.trim() : '');

const clampText = (value: string, maxLen: number): string => {
  const text = value.trim();
  if (!text || text.length <= maxLen) return text;
  return text.slice(0, Math.max(0, maxLen - 1)).trimEnd() + '...';
};

const isTaskDone = (task: PmTask): boolean => {
  if (task.completed || task.done) return true;
  const status = String(task.status || task.state || '').toLowerCase();
  return ['done', 'complete', 'completed', 'success', 'passed', 'pass', 'ok'].some((key) =>
    status.includes(key)
  );
};

const taskKey = (task: PmTask): string => task.id || toText(task.title) || toText(task.goal);

const pickTaskSummary = (task: PmTask): string => task.summary || task.title || task.goal || '';

export function ProjectProgressPanel({
  tasks,
  pmState,
  focus,
  notes,
  goals,
  planText,
  planMtime,
  successStats,
  pmRunning,
  className,
}: ProjectProgressPanelProps) {
  const normalizedTasks = Array.isArray(tasks)
    ? tasks.filter((task): task is PmTask => Boolean(task && typeof task === 'object'))
    : [];
  const totalTasks = normalizedTasks.length;
  const completedIdsRaw = Array.isArray(pmState?.completed_task_ids) ? pmState.completed_task_ids : [];
  const completedIds = completedIdsRaw
    .map((item: unknown) => (typeof item === 'string' ? item.trim() : ''))
    .filter((item: string) => item.length > 0);

  const completedSet = new Set(completedIds);
  const completedInList = normalizedTasks.filter((task) => completedSet.has(taskKey(task))).length;
  const doneCount = normalizedTasks.filter((task) => isTaskDone(task) || completedSet.has(taskKey(task))).length;
  const completedCount = totalTasks > 0
    ? Math.max(doneCount, completedInList)
    : typeof pmState?.completed_task_count === 'number'
      ? pmState.completed_task_count
      : completedSet.size;
  const lastTaskId = toText(pmState?.last_director_task_id);
  const lastTaskTitle = toText(pmState?.last_director_task_title);
  const lastStatus = toText(pmState?.last_director_status).toLowerCase();
  const lastUpdated = toText(pmState?.last_updated_ts);
  const iterationRaw = pmState?.pm_iteration;
  const iteration =
    typeof iterationRaw === 'number'
      ? iterationRaw
      : typeof iterationRaw === 'string'
        ? Number(iterationRaw)
        : null;

  const nextPendingTask = normalizedTasks.find((task) => {
    const key = taskKey(task);
    if (!key) return false;
    return !completedSet.has(key) && !isTaskDone(task);
  });
  const currentIndex = normalizedTasks.findIndex(
    (task) => (lastTaskId && task.id === lastTaskId) || (lastTaskTitle && task.title === lastTaskTitle),
  );
  const currentTask = nextPendingTask || (currentIndex >= 0 ? normalizedTasks[currentIndex] : undefined);
  const fallbackTaskTitle = currentTask?.title || currentTask?.goal || lastTaskTitle;
  const positionIndex = currentIndex >= 0 ? currentIndex : totalTasks > 0 ? 0 : -1;
  const queueItems = normalizedTasks.map((task, idx) => {
    const key = taskKey(task) || `${idx + 1}`;
    const title = task.title || task.goal || task.id || `Task ${idx + 1}`;
    const isCompleted = completedSet.has(taskKey(task)) || isTaskDone(task);
    const isCurrent = currentTask && taskKey(currentTask) === taskKey(task);
    return { key, title, id: task.id, isCompleted, isCurrent };
  });

  let progress = 0;
  let progressHint = '等待 PM 输出任务';
  let progressMode: 'done' | 'position' | 'success' | 'idle' = 'idle';

  if (totalTasks > 0 && completedCount > 0) {
    progress = completedCount / totalTasks;
    progressHint = `已完成 ${Math.min(completedCount, totalTasks)}/${totalTasks}`;
    progressMode = 'done';
  } else if (totalTasks > 0 && positionIndex >= 0) {
    progress = (positionIndex + 1) / totalTasks;
    progressHint = `当前任务 ${positionIndex + 1}/${totalTasks}（估算）`;
    progressMode = 'position';
  } else if (typeof successStats?.rate === 'number') {
    progress = successStats.rate;
    progressHint = `历史成功率 ${Math.round(progress * 100)}%（估算）`;
    progressMode = 'success';
  }

  progress = Math.max(0, Math.min(1, progress));
  const progressPct = Math.round(progress * 100);

  const statusTone =
    lastStatus === 'success'
      ? 'text-emerald-300'
      : lastStatus === 'blocked'
        ? 'text-amber-300'
        : lastStatus === 'failure'
          ? 'text-red-300'
          : 'text-slate-300';

  const statusIcon =
    lastStatus === 'success' ? (
      <CheckCircle className="size-4 text-emerald-300" />
    ) : lastStatus === 'blocked' ? (
      <AlertTriangle className="size-4 text-amber-300" />
    ) : (
      <Activity className="size-4 text-slate-300" />
    );

  const focusText = focus ? clampText(focus, 160) : '';
  const notesText = notes ? clampText(notes, 180) : '';
  const currentSummary = clampText(pickTaskSummary(currentTask || { title: lastTaskTitle }), 160);
  const goalList = Array.isArray(goals) ? goals.filter((item) => typeof item === 'string' && item.trim().length > 0) : [];
  const planPreview = typeof planText === 'string' ? planText.trim() : '';
  const planUpdated = typeof planMtime === 'string' ? planMtime : '';

  return (
    <div
      className={`border-b border-white/5 bg-transparent px-5 py-4 flex flex-col min-h-0 ${className || ''}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-white/5 text-accent">
            <Target className="size-5" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-heading font-bold text-text-main">PM 项目进度</span>
              {pmRunning ? (
                <span className="rounded-full bg-status-success/10 px-2 py-0.5 text-[11px] text-status-success shadow-[0_0_8px_rgba(16,185,129,0.3)] animate-pulse">Running</span>
              ) : (
                <span className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-text-dim">Idle</span>
              )}
              {iteration !== null && Number.isFinite(iteration) ? (
                <span className="rounded-full bg-accent/10 px-2 py-0.5 text-[11px] text-accent-text border border-accent/20">
                  Iteration {iteration}
                </span>
              ) : null}
            </div>
            <div className="mt-1 text-xs text-text-muted">
              {focusText || notesText ? (
                <>
                  {focusText ? <span>目标: <span className="text-text-main">{focusText}</span></span> : null}
                  {focusText && notesText ? <span className="mx-2 text-white/10">|</span> : null}
                  {notesText ? <span>备注: {notesText}</span> : null}
                </>
              ) : (
                <span>PM 正在整理任务与目标</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-text-main backdrop-blur-sm">
          {statusIcon}
          <span className={`font-mono ${statusTone}`}>{lastStatus ? lastStatus.toUpperCase() : 'NO STATUS'}</span>
          {lastUpdated ? (
            <>
              <span className="text-white/10">|</span>
              <Clock className="size-3 text-text-dim" />
              <span className="text-text-dim">{lastUpdated}</span>
            </>
          ) : null}
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur-md hover:border-accent/30 transition-all">
          <div className="flex items-center justify-between gap-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-text-muted">整体完成度</div>
            <div className="text-xs text-text-dim font-mono">{progressHint}</div>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/5">
            <div
              className="h-full rounded-full bg-gradient-primary shadow-[0_0_10px_rgba(124,58,237,0.5)] transition-all duration-500"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <div className="mt-2 flex items-center justify-between text-xs text-text-muted">
            <span>{progressMode === 'done' ? '已完成' : progressMode === 'position' ? '进行中' : '估算'}</span>
            <span className="text-accent font-mono font-bold">{progressPct}%</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-text-dim">
            <span className="rounded-full border border-white/10 px-2 py-0.5 hover:bg-white/5 transition-colors">
              总任务: {totalTasks || '-'}
            </span>
            <span className="rounded-full border border-white/10 px-2 py-0.5 hover:bg-white/5 transition-colors">
              已完成: {totalTasks ? completedCount : '-'}
            </span>
            {typeof successStats?.successes === 'number' && typeof successStats?.total === 'number' ? (
              <span className="rounded-full border border-white/10 px-2 py-0.5 hover:bg-white/5 transition-colors">
                Director 成功率: {Math.round((successStats.rate ?? 0) * 100)}%
              </span>
            ) : null}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur-md hover:border-accent/30 transition-all">
          <div className="flex items-center justify-between gap-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-text-muted">{'\u5f53\u524d Director \u4efb\u52a1'}</div>
            <ArrowRight className="size-4 text-accent animate-pulse" />
          </div>
          {currentSummary ? (
            <div className="mt-3 flex items-start gap-3">
              <div className="mt-1 flex size-8 items-center justify-center rounded-full bg-accent/20 text-accent shadow-[0_0_10px_rgba(124,58,237,0.3)]">
                <ArrowRight className="size-4" />
              </div>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-text-main">{currentSummary}</div>
                <div className="mt-1 text-xs text-text-dim font-mono">
                  {lastTaskId ? <span>ID: {lastTaskId}</span> : <span>{'\u7b49\u5f85 PM \u5206\u914d\u4efb\u52a1'}</span>}
                </div>
              </div>
            </div>
          ) : (
            <div className="mt-3 text-sm text-text-dim">{'\u6682\u65e0\u5f53\u524d\u4efb\u52a1\u4fe1\u606f'}</div>
          )}

          <div className="mt-4 border-t border-white/5 pt-3">
            <div className="flex items-center justify-between text-xs text-text-muted">
              <span className="font-medium uppercase tracking-wide">{'PM \u2192 Director \u4efb\u52a1\u961f\u5217'}</span>
              <span className="font-mono">{queueItems.length ? `${queueItems.length} \u9879` : '-'}</span>
            </div>
            <div className="mt-2 max-h-40 space-y-1 overflow-auto pr-1 custom-scrollbar">
              {queueItems.length === 0 ? (
                <div className="text-xs text-text-dim">{'\u6682\u65e0\u5206\u914d\u4efb\u52a1'}</div>
              ) : (
                queueItems.map((item, idx) => (
                  <div
                    key={`${item.key}-${idx}`}
                    className={`flex items-center justify-between gap-2 rounded-md px-2 py-1 text-xs transition-colors ${item.isCurrent
                      ? 'bg-accent/20 text-accent border border-accent/20'
                      : item.isCompleted
                        ? 'bg-status-success/10 text-status-success/80'
                        : 'bg-white/5 text-text-dim hover:bg-white/10'
                      }`}
                  >
                    <div className="min-w-0 flex-1 truncate">
                      <span className="text-text-dim/50 mr-2 font-mono">#{idx + 1}</span>
                      {item.title}
                    </div>
                    <span className="shrink-0 text-[10px] opacity-70">
                      {item.isCompleted ? '\u5df2\u5b8c\u6210' : item.isCurrent ? '\u8fdb\u884c\u4e2d' : '\u5f85\u5f00\u59cb'}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-white/5 bg-white/5 p-4 backdrop-blur-sm">
        <div className="flex items-center justify-between text-xs text-text-muted">
          <span className="font-medium uppercase tracking-wide">{'\u5168\u90e8\u76ee\u6807'}</span>
          <span className="font-mono">{goalList.length ? `${goalList.length} \u9879` : '-'}</span>
        </div>
        <div className="mt-3 max-h-40 space-y-2 overflow-auto pr-1 text-xs text-text-main custom-scrollbar">
          {goalList.length === 0 ? (
            <div className="text-text-dim">{'\u6682\u65e0\u76ee\u6807'}</div>
          ) : (
            goalList.map((item, idx) => (
              <div key={`${idx}-${item}`} className="flex items-start gap-2">
                <span className="mt-0.5 text-accent font-mono text-[10px]">{idx + 1}.</span>
                <span className="leading-relaxed">{item}</span>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-white/5 bg-white/5 p-4 backdrop-blur-sm">
        <div className="flex items-center justify-between text-xs text-text-muted">
          <span className="font-medium uppercase tracking-wide">{'\u603b\u89c4\u5212 (PLAN.md)'}</span>
          {planUpdated ? <span className="text-text-dim font-mono">{planUpdated}</span> : <span className="text-text-dim">-</span>}
        </div>
        <div className="mt-3 max-h-56 overflow-auto rounded-xl border border-white/5 bg-bg-panel/50 px-3 py-2 text-xs text-text-code whitespace-pre-wrap leading-relaxed custom-scrollbar shadow-inner">
          {planPreview || '\u6682\u65e0\u603b\u89c4\u5212'}
        </div>
      </div>

      <div className="mt-4 flex min-h-0 flex-1 flex-col">
        <div className="mb-2 flex items-center justify-between text-xs text-text-muted">
          <div className="flex items-center gap-2">
            <ListChecks className="size-4 text-text-dim" />
            <span className="font-medium uppercase tracking-wide">{'\u4efb\u52a1\u89c4\u5212\uff08PM \u2192 Director\uff09'}</span>
          </div>
          <span className="font-mono">{totalTasks ? `${totalTasks} \u9879` : '\u6682\u65e0\u4efb\u52a1'}</span>
        </div>
        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-auto pr-1 custom-scrollbar">
          {normalizedTasks.length === 0 ? (
            <div className="col-span-full rounded-xl border border-dashed border-white/10 bg-white/5 p-6 text-center text-sm text-text-dim">
              等待 PM 生成任务清单...
            </div>
          ) : (
            normalizedTasks.map((task, index) => {
              const key = taskKey(task);
              const isCompleted = completedSet.has(key) || isTaskDone(task);
              const isCurrent = currentTask && taskKey(currentTask) === key;
              const title = task.title || task.goal || task.id || `Task ${index + 1}`;
              const goal = task.goal && task.goal !== title ? task.goal : '';
              const acceptance = Array.isArray(task.acceptance)
                ? task.acceptance.filter((item) => typeof item === 'string' && item.trim().length > 0).slice(0, 3)
                : [];

              return (
                <div
                  key={`${key || title}-${index}`}
                  className={`rounded-xl border p-3 transition-all duration-300 ${isCurrent
                    ? 'border-accent/50 bg-accent/5 shadow-[0_0_15px_rgba(124,58,237,0.1)]'
                    : isCompleted
                      ? 'border-status-success/30 bg-status-success/5 opacity-80'
                      : 'border-white/5 bg-white/5 hover:border-white/10 hover:bg-white/10'
                    }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 text-xs text-text-dim font-mono">
                        <span>#{index + 1}</span>
                        {task.id ? <span className="rounded-full border border-white/10 px-2 py-0.5">ID: {task.id}</span> : null}
                        {task.priority !== undefined ? (
                          <span className="rounded-full border border-white/10 px-2 py-0.5">P{task.priority}</span>
                        ) : null}
                      </div>
                      <div className="mt-1 text-sm font-semibold text-text-main">{clampText(title, 120)}</div>
                      {goal ? <div className="mt-2 text-xs text-text-muted">{clampText(goal, 180)}</div> : null}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-text-dim">
                      {isCompleted ? (
                        <CheckCircle className="size-4 text-status-success" />
                      ) : isCurrent ? (
                        <ArrowRight className="size-4 text-accent animate-pulse" />
                      ) : (
                        <Clock className="size-4 text-text-dim" />
                      )}
                      <span className="rounded-full border border-white/10 px-2 py-0.5 backdrop-blur-sm">
                        {isCompleted ? '已完成' : isCurrent ? '进行中' : '待开始'}
                      </span>
                    </div>
                  </div>
                  {acceptance.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-text-muted">
                      {acceptance.map((item, idx) => (
                        <span key={`${key}-acc-${idx}`} className="rounded-full bg-bg-surface/50 px-2 py-0.5 border border-white/5">
                          {clampText(String(item), 80)}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
