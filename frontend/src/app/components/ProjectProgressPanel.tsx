import { Activity, AlertTriangle, ArrowRight, CheckCircle, Clock, ListChecks, Target } from 'lucide-react';
import type { PmTask, SuccessStats, PmState, TaskQueueItem, ProgressMode } from '@/types/task';
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
    .filter((item: string) => item.length > 0) as string[];

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
  const currentSummaryRaw = currentTask ? pickTaskSummary(currentTask) : (lastTaskTitle || '');
  const currentSummary = clampText(currentSummaryRaw, 160);
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
        <ProgressBar
          progress={progress}
          progressHint={progressHint}
          progressMode={progressMode}
          totalTasks={totalTasks}
          completedCount={completedCount}
          successRate={successStats?.rate}
        />

        <div className="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur-md hover:border-accent/30 transition-all flex flex-col h-full">
           <CurrentTaskCard
              currentSummary={currentSummary}
              lastTaskId={lastTaskId}
           />
           <div className="mt-4 border-t border-white/5 pt-3 flex-1 min-h-0 flex flex-col">
              <TaskQueue
                queueItems={queueItems}
              />
           </div>
        </div>
      </div>

      <GoalsList goals={goalList} />

      <PlanPreview planText={planPreview} planUpdated={planUpdated} />

      <div className="mt-4 flex min-h-0 flex-1 flex-col">
        <div className="mb-2 flex items-center justify-between text-xs text-text-muted">
          <div className="flex items-center gap-2">
            <ListChecks className="size-4 text-text-dim" />
            <span className="font-medium uppercase tracking-wide">{'\u4efb\u52a1\u89c4\u5212\uff08PM \u2192 Director\uff09'}</span>
          </div>
          <span className="font-mono">{totalTasks ? `${totalTasks} \u9879` : '\u6682\u65e0\u4efb\u52a1'}</span>
        </div>
        <TaskList
          tasks={normalizedTasks}
          completedSet={completedSet}
          currentTaskKey={currentTask ? taskKey(currentTask) : undefined}
          taskKey={taskKey}
          isTaskDone={isTaskDone}
          clampText={clampText}
        />
      </div>
    </div>
  );
}
