import { Activity, AlertTriangle, ArrowRight, CheckCircle, Clock, ListChecks, Target } from 'lucide-react';

type PmTask = {
  id?: string;
  title?: string;
  goal?: string;
  summary?: string;
  status?: string;
  state?: string;
  done?: boolean;
  completed?: boolean;
  priority?: number;
  acceptance?: unknown[];
};

type SuccessStats = {
  successes?: number | null;
  total?: number | null;
  rate?: number | null;
};

interface ProjectProgressPanelProps {
  tasks: PmTask[];
  pmState?: Record<string, unknown> | null;
  focus?: string | null;
  notes?: string | null;
  goals?: string[] | null;
  planText?: string | null;
  planMtime?: string | null;
  successStats?: SuccessStats | null;
  pmRunning?: boolean;
  className?: string;
}

function toText(value: unknown) {
  return typeof value === 'string' ? value.trim() : '';
}

function clampText(value: string, maxLen: number) {
  const text = value.trim();
  if (!text) return '';
  if (text.length <= maxLen) return text;
  return text.slice(0, Math.max(0, maxLen - 1)).trimEnd() + '...';
}

function isTaskDone(task: PmTask) {
  if (task.completed || task.done) return true;
  const status = (task.status || task.state || '').toLowerCase();
  return ['done', 'complete', 'completed', 'success', 'passed', 'pass', 'ok'].some((key) => status.includes(key));
}

function taskKey(task: PmTask) {
  return toText(task.id) || toText(task.title) || toText(task.goal);
}

function pickTaskSummary(task: PmTask) {
  return task.summary || task.title || task.goal || '';
}

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
  const completedIdsRaw = Array.isArray(pmState?.completed_task_ids) ? pmState?.completed_task_ids : [];
  const completedIds = completedIdsRaw
    .map((item) => (typeof item === 'string' ? item.trim() : ''))
    .filter((item) => item.length > 0);
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
      className={`border-b border-gray-800 bg-gradient-to-br from-[#161a22] via-[#1b202a] to-[#12151b] px-5 py-4 flex flex-col min-h-0 ${className || ''}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-200">
            <Target className="size-5" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-slate-100">PM 项目进度</span>
              {pmRunning ? (
                <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] text-emerald-200">Running</span>
              ) : (
                <span className="rounded-full bg-slate-500/15 px-2 py-0.5 text-[11px] text-slate-300">Idle</span>
              )}
              {iteration !== null && Number.isFinite(iteration) ? (
                <span className="rounded-full bg-slate-500/15 px-2 py-0.5 text-[11px] text-slate-300">
                  Iteration {iteration}
                </span>
              ) : null}
            </div>
            <div className="mt-1 text-xs text-slate-400">
              {focusText || notesText ? (
                <>
                  {focusText ? <span>目标: {focusText}</span> : null}
                  {focusText && notesText ? <span className="mx-2 text-slate-600">|</span> : null}
                  {notesText ? <span>备注: {notesText}</span> : null}
                </>
              ) : (
                <span>PM 正在整理任务与目标</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-slate-700/60 bg-[#0f1117] px-3 py-2 text-xs text-slate-300">
          {statusIcon}
          <span className={statusTone}>{lastStatus ? lastStatus.toUpperCase() : 'NO STATUS'}</span>
          {lastUpdated ? (
            <>
              <span className="text-slate-600">|</span>
              <Clock className="size-3 text-slate-500" />
              <span className="text-slate-400">{lastUpdated}</span>
            </>
          ) : null}
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <div className="rounded-2xl border border-slate-800/70 bg-[#0f1117] p-4">
          <div className="flex items-center justify-between gap-2">
            <div className="text-xs font-medium uppercase tracking-wide text-slate-400">整体完成度</div>
            <div className="text-xs text-slate-400">{progressHint}</div>
          </div>
          <div className="mt-3 h-3 overflow-hidden rounded-full bg-slate-800/80">
            <div
              className="h-full rounded-full bg-gradient-to-r from-emerald-400 via-sky-400 to-blue-400 transition-all"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
            <span>{progressMode === 'done' ? '已完成' : progressMode === 'position' ? '进行中' : '估算'}</span>
            <span className="text-slate-200">{progressPct}%</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-400">
            <span className="rounded-full border border-slate-700/60 px-2 py-0.5">
              总任务: {totalTasks || '-'}
            </span>
            <span className="rounded-full border border-slate-700/60 px-2 py-0.5">
              已完成: {totalTasks ? completedCount : '-'}
            </span>
            {typeof successStats?.successes === 'number' && typeof successStats?.total === 'number' ? (
              <span className="rounded-full border border-slate-700/60 px-2 py-0.5">
                Director 成功率: {Math.round((successStats.rate ?? 0) * 100)}%
              </span>
            ) : null}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800/70 bg-[#0f1117] p-4">
          <div className="flex items-center justify-between gap-2">
            <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{'\u5f53\u524d Director \u4efb\u52a1'}</div>
            <ArrowRight className="size-4 text-emerald-300" />
          </div>
          {currentSummary ? (
            <div className="mt-3 flex items-start gap-3">
              <div className="mt-1 flex size-8 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-200">
                <ArrowRight className="size-4" />
              </div>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-slate-100">{currentSummary}</div>
                <div className="mt-1 text-xs text-slate-400">
                  {lastTaskId ? <span>ID: {lastTaskId}</span> : <span>{'\u7b49\u5f85 PM \u5206\u914d\u4efb\u52a1'}</span>}
                </div>
              </div>
            </div>
          ) : (
            <div className="mt-3 text-sm text-slate-500">{'\u6682\u65e0\u5f53\u524d\u4efb\u52a1\u4fe1\u606f'}</div>
          )}

          <div className="mt-4 border-t border-slate-800/60 pt-3">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span className="font-medium uppercase tracking-wide">{'PM \u2192 Director \u4efb\u52a1\u961f\u5217'}</span>
              <span>{queueItems.length ? `${queueItems.length} \u9879` : '-'}</span>
            </div>
            <div className="mt-2 max-h-40 space-y-1 overflow-auto pr-1">
              {queueItems.length === 0 ? (
                <div className="text-xs text-slate-500">{'\u6682\u65e0\u5206\u914d\u4efb\u52a1'}</div>
              ) : (
                queueItems.map((item, idx) => (
                  <div
                    key={`${item.key}-${idx}`}
                    className={`flex items-center justify-between gap-2 rounded-md px-2 py-1 text-xs ${
                      item.isCurrent
                        ? 'bg-emerald-500/10 text-emerald-200'
                        : item.isCompleted
                          ? 'bg-emerald-500/5 text-emerald-300/80'
                          : 'bg-slate-800/40 text-slate-300'
                    }`}
                  >
                    <div className="min-w-0 flex-1 truncate">
                      <span className="text-slate-500 mr-2">#{idx + 1}</span>
                      {item.title}
                    </div>
                    <span className="shrink-0 text-[10px] text-slate-400">
                      {item.isCompleted ? '\u5df2\u5b8c\u6210' : item.isCurrent ? '\u8fdb\u884c\u4e2d' : '\u5f85\u5f00\u59cb'}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-slate-800/70 bg-[#0f1117] p-4">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span className="font-medium uppercase tracking-wide">{'\u5168\u90e8\u76ee\u6807'}</span>
          <span>{goalList.length ? `${goalList.length} \u9879` : '-'}</span>
        </div>
        <div className="mt-3 max-h-40 space-y-2 overflow-auto pr-1 text-xs text-slate-300">
          {goalList.length === 0 ? (
            <div className="text-slate-500">{'\u6682\u65e0\u76ee\u6807'}</div>
          ) : (
            goalList.map((item, idx) => (
              <div key={`${idx}-${item}`} className="flex items-start gap-2">
                <span className="mt-0.5 text-slate-500">{idx + 1}.</span>
                <span className="leading-relaxed">{item}</span>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-slate-800/70 bg-[#0f1117] p-4">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span className="font-medium uppercase tracking-wide">{'\u603b\u89c4\u5212 (PLAN.md)'}</span>
          {planUpdated ? <span className="text-slate-500">{planUpdated}</span> : <span className="text-slate-600">-</span>}
        </div>
        <div className="mt-3 max-h-56 overflow-auto rounded-xl border border-slate-800/60 bg-slate-950/40 px-3 py-2 text-xs text-slate-200 whitespace-pre-wrap leading-relaxed">
          {planPreview || '\u6682\u65e0\u603b\u89c4\u5212'}
        </div>
      </div>

      <div className="mt-4 flex min-h-0 flex-1 flex-col">
        <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <ListChecks className="size-4 text-slate-300" />
            <span className="font-medium uppercase tracking-wide">{'\u4efb\u52a1\u89c4\u5212\uff08PM \u2192 Director\uff09'}</span>
          </div>
          <span>{totalTasks ? `${totalTasks} \u9879` : '\u6682\u65e0\u4efb\u52a1'}</span>
        </div>
        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-auto pr-1">
          {normalizedTasks.length === 0 ? (
            <div className="col-span-full rounded-xl border border-dashed border-slate-700/70 bg-[#0f1117] p-6 text-center text-sm text-slate-500">
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
                  className={`rounded-xl border p-3 transition ${
                    isCurrent
                      ? 'border-emerald-500/50 bg-emerald-500/10 shadow-[0_0_0_1px_rgba(16,185,129,0.2)]'
                      : isCompleted
                        ? 'border-emerald-900/60 bg-emerald-500/5'
                        : 'border-slate-800/70 bg-[#0f1117]'
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 text-xs text-slate-500">
                        <span>#{index + 1}</span>
                        {task.id ? <span className="rounded-full border border-slate-700/60 px-2 py-0.5">ID: {task.id}</span> : null}
                        {task.priority !== undefined ? (
                          <span className="rounded-full border border-slate-700/60 px-2 py-0.5">P{task.priority}</span>
                        ) : null}
                      </div>
                      <div className="mt-1 text-sm font-semibold text-slate-100">{clampText(title, 120)}</div>
                      {goal ? <div className="mt-2 text-xs text-slate-400">{clampText(goal, 180)}</div> : null}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                      {isCompleted ? (
                        <CheckCircle className="size-4 text-emerald-300" />
                      ) : isCurrent ? (
                        <ArrowRight className="size-4 text-emerald-300" />
                      ) : (
                        <Clock className="size-4 text-slate-500" />
                      )}
                      <span className="rounded-full border border-slate-700/60 px-2 py-0.5">
                        {isCompleted ? '已完成' : isCurrent ? '进行中' : '待开始'}
                      </span>
                    </div>
                  </div>
                  {acceptance.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-300">
                      {acceptance.map((item, idx) => (
                        <span key={`${key}-acc-${idx}`} className="rounded-full bg-slate-800/80 px-2 py-0.5">
                          {clampText(item, 80)}
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
