import { FileText, ListChecks, StickyNote, Target } from 'lucide-react';

interface SnapshotPanelProps {
  timestamp?: string | null;
  focus?: string | null;
  notes?: string | null;
  tasks?: unknown[] | null;
  fileStatus?: string[] | null;
  filePaths?: string[] | null;
  directorState?: Record<string, unknown> | null;
}

function clampText(value: string, maxLen: number) {
  const text = value.trim();
  if (!text) return '';
  if (text.length <= maxLen) return text;
  return text.slice(0, Math.max(0, maxLen - 1)).trimEnd() + '…';
}

export function SnapshotPanel({ timestamp, focus, notes, tasks, fileStatus, filePaths, directorState }: SnapshotPanelProps) {
  const taskCount = Array.isArray(tasks) ? tasks.length : null;
  const focusText = focus ? clampText(focus, 160) : '';
  const notesText = notes ? clampText(notes, 200) : '';
  const fileLines = Array.isArray(fileStatus) ? fileStatus.slice(0, 4) : [];
  const filePathsCount = Array.isArray(filePaths) ? filePaths.length : 0;
  const directorPhase = directorState && typeof directorState['phase'] === 'string' ? String(directorState['phase']) : '';
  const directorIter = directorState && typeof directorState['iteration'] === 'number' ? Number(directorState['iteration']) : null;
  const directorStatus = directorState && typeof directorState['status'] === 'string' ? String(directorState['status']) : '';

  return (
    <div className="border-b border-border bg-bg-panel/90 px-4 py-2 text-xs text-text-dim backdrop-blur-sm z-10">
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 flex-1 items-start gap-4">
          <div className="flex min-w-0 flex-1 items-start gap-2 group">
            <Target className="mt-0.5 size-3 text-status-info flex-shrink-0 group-hover:text-accent transition-colors" />
            <div className="min-w-0">
              <div className="text-[10px] uppercase font-bold tracking-wider text-text-muted mb-0.5">Focus</div>
              <div className="truncate text-text-main font-medium">{focusText || '-'}</div>
            </div>
          </div>
          <div className="flex min-w-0 flex-1 items-start gap-2 group">
            <StickyNote className="mt-0.5 size-3 text-status-success flex-shrink-0 group-hover:text-status-success/80 transition-colors" />
            <div className="min-w-0">
              <div className="text-[10px] uppercase font-bold tracking-wider text-text-muted mb-0.5">Notes</div>
              <div className="truncate text-text-main font-medium">{notesText || '-'}</div>
            </div>
          </div>
        </div>

        <div className="flex flex-shrink-0 items-center gap-4 text-text-dim font-mono text-[10px]">
          <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-bg-tertiary border border-border">
            <ListChecks className="size-3 text-status-secondary" />
            <span>TASKS: <span className="text-text-main">{taskCount ?? '—'}</span></span>
          </div>

          <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-bg-tertiary border border-border">
            <FileText className="size-3 text-text-muted" />
            <span>TS: <span className="text-text-main">{timestamp || '—'}</span></span>
          </div>

          <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-bg-tertiary border border-border">
            <span>FILES: <span className="text-text-main">{filePathsCount}</span></span>
          </div>

          {directorPhase || directorStatus || directorIter !== null ? (
            <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-bg-tertiary border border-border animate-pulse-slow">
              <span className="text-status-secondary font-bold">DIRECTOR</span>
              <span className="w-px h-3 bg-border mx-1"></span>
              <span className="text-text-main">{directorPhase || directorStatus || ''}</span>
              {directorIter !== null ? <span className="text-accent"> #{directorIter}</span> : ''}
            </div>
          ) : null}
        </div>
      </div>

      {fileLines.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-mono text-text-dim border-t border-border pt-2 bg-bg-tertiary/20 -mx-4 px-4 pb-1">
          {fileLines.map((line) => (
            <span key={line} className="truncate max-w-[28rem] flex items-center gap-1">
              <span className="w-1 h-1 rounded-full bg-text-muted"></span>
              {line}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
