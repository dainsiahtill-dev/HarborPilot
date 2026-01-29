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
    <div className="border-b border-gray-800 bg-[#252526] px-4 py-2 text-xs text-gray-300">
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 flex-1 items-start gap-4">
          <div className="flex min-w-0 flex-1 items-start gap-2">
            <Target className="mt-0.5 size-3 text-blue-400 flex-shrink-0" />
            <div className="min-w-0">
              <div className="text-gray-500">Focus</div>
              <div className="truncate">{focusText || '-'}</div>
            </div>
          </div>
          <div className="flex min-w-0 flex-1 items-start gap-2">
            <StickyNote className="mt-0.5 size-3 text-green-400 flex-shrink-0" />
            <div className="min-w-0">
              <div className="text-gray-500">Notes</div>
              <div className="truncate">{notesText || '-'}</div>
            </div>
          </div>
        </div>

        <div className="flex flex-shrink-0 items-center gap-4 text-gray-400">
          <div className="flex items-center gap-1">
            <ListChecks className="size-3 text-purple-400" />
            <span>Tasks: {taskCount ?? '—'}</span>
          </div>
          <div className="flex items-center gap-1">
            <FileText className="size-3 text-gray-400" />
            <span>{timestamp || '—'}</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-gray-500">|</span>
            <span>Files: {filePathsCount}</span>
          </div>
          {directorPhase || directorStatus || directorIter !== null ? (
            <div className="flex items-center gap-1">
              <span className="text-gray-500">|</span>
              <span>Director {directorPhase || directorStatus || ''}{directorIter !== null ? ` #${directorIter}` : ''}</span>
            </div>
          ) : null}
        </div>
      </div>

      {fileLines.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-gray-500">
          {fileLines.map((line) => (
            <span key={line} className="truncate max-w-[28rem]">
              {line}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
