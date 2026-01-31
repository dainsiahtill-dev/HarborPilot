import { FileJson, FileText, MessageSquare, Activity, Folder, ChevronDown, ChevronRight, History } from 'lucide-react';
import { useState } from 'react';

interface ArtifactItem {
  id: string;
  name: string;
  icon: any;
  path: string;
  badge?: string;
}

interface ArtifactGroup {
  name: string;
  items: ArtifactItem[];
}

const artifactGroups: ArtifactGroup[] = [
  {
    name: 'PM 产物',
    items: [
      { id: 'pm-tasks', name: 'PM_TASKS.json', icon: FileJson, path: '.harborpilot/runtime/PM_TASKS.json', badge: 'Contract' },
      { id: 'pm-report', name: 'PM_REPORT.md', icon: FileText, path: '.harborpilot/runtime/PM_REPORT.md' },
      { id: 'plan', name: 'PLAN.md', icon: FileText, path: '.harborpilot/runtime/PLAN.md' },
      { id: 'pm-state', name: 'PM_STATE.json', icon: FileJson, path: '.harborpilot/runtime/PM_STATE.json' },
    ],
  },
  {
    name: 'Director 产物',
    items: [
      { id: 'director-result', name: 'DIRECTOR_RESULT.json', icon: FileJson, path: '.harborpilot/runtime/DIRECTOR_RESULT.json', badge: 'Result' },
      { id: 'planner', name: 'PLANNER_RESPONSE.md', icon: FileText, path: '.harborpilot/runtime/PLANNER_RESPONSE.md' },
      { id: 'ollama', name: 'OLLAMA_RESPONSE.md', icon: FileText, path: '.harborpilot/runtime/OLLAMA_RESPONSE.md' },
      { id: 'runlog', name: 'RUNLOG.md', icon: FileText, path: '.harborpilot/runtime/RUNLOG.md' },
      { id: 'director-subprocess', name: 'DIRECTOR_SUBPROCESS.log', icon: FileText, path: '.harborpilot/runtime/DIRECTOR_SUBPROCESS.log' },
    ],
  },
  {
    name: 'QA & Review',
    items: [
      { id: 'qa', name: 'QA_RESPONSE.md', icon: FileText, path: '.harborpilot/runtime/QA_RESPONSE.md', badge: 'QA' },
      { id: 'review', name: 'REVIEW_RESPONSE.md', icon: FileText, path: '.harborpilot/runtime/REVIEW_RESPONSE.md' },
      { id: 'gap', name: 'GAP_REPORT.md', icon: FileText, path: '.harborpilot/runtime/GAP_REPORT.md' },
    ],
  },
  {
    name: '事件流',
    items: [
      { id: 'dialogue', name: 'DIALOGUE.jsonl', icon: MessageSquare, path: '.harborpilot/runtime/DIALOGUE.jsonl' },
      { id: 'events', name: 'events.jsonl', icon: Activity, path: '.harborpilot/runtime/events.jsonl' },
      { id: 'trajectory', name: 'trajectory.json', icon: FileJson, path: '.harborpilot/runtime/trajectory.json' },
    ],
  },
  {
    name: 'Config & Memory',
    items: [
      { id: 'policy', name: 'director_policy.json', icon: FileJson, path: '.harborpilot/runtime/director_policy.json' },
      { id: 'memory', name: 'last_state.json', icon: FileJson, path: '.harborpilot/runtime/memory/last_state.json' },
    ],
  },
];

interface ArtifactsSidebarProps {
  onFileSelect: (file: ArtifactItem) => void;
  selectedFileId: string | null;
  onOpenWorkspace?: () => void;
  onOpenHistory?: () => void;
  fileStatusLines?: string[] | null;
}

export function ArtifactsSidebar({ onFileSelect, selectedFileId, onOpenWorkspace, onOpenHistory, fileStatusLines }: ArtifactsSidebarProps) {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(
    new Set(artifactGroups.map((g) => g.name))
  );

  const toggleGroup = (groupName: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(groupName)) {
        next.delete(groupName);
      } else {
        next.add(groupName);
      }
      return next;
    });
  };

  return (
    <div className="h-full bg-[#1e1e1e] border-r border-gray-800 flex flex-col">
      <div className="px-4 py-3 border-b border-gray-800">
        <h2 className="text-sm font-semibold text-gray-300">运行产物</h2>
        <p className="text-xs text-gray-500 mt-1">.harborpilot/runtime/</p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {artifactGroups.map((group) => {
          const isExpanded = expandedGroups.has(group.name);
          return (
            <div key={group.name} className="border-b border-gray-800/50">
              <button
                onClick={() => toggleGroup(group.name)}
                className="w-full flex items-center gap-2 px-4 py-2 hover:bg-white/5 transition-colors"
              >
                {isExpanded ? (
                  <ChevronDown className="size-4 text-gray-400" />
                ) : (
                  <ChevronRight className="size-4 text-gray-400" />
                )}
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
                  {group.name}
                </span>
              </button>

              {isExpanded && (
                <div className="pb-2">
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    const isSelected = selectedFileId === item.id;
                    let badgeText: string | undefined = item.badge;
                    if (Array.isArray(fileStatusLines)) {
                      for (const line of fileStatusLines) {
                        const idx = line.indexOf(':');
                        if (idx > 0) {
                          const label = line.slice(0, idx).trim();
                          const value = line.slice(idx + 1).trim();
                          if (label === item.name) {
                            badgeText = value;
                            break;
                          }
                        }
                      }
                    }
                    return (
                      <button
                        key={item.id}
                        onClick={() => onFileSelect(item)}
                        className={`w-full flex items-center gap-2 px-4 py-1.5 pl-10 hover:bg-white/5 transition-colors ${
                          isSelected ? 'bg-white/10' : ''
                        }`}
                      >
                        <Icon className="size-4 text-gray-400 flex-shrink-0" />
                        <span className="text-sm text-gray-300 truncate flex-1 text-left">
                          {item.name}
                        </span>
                        {badgeText && (
                          <span className="text-xs px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400">
                            {badgeText}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 快速链接 */}
      <div className="border-t border-gray-800 p-2 space-y-1">
        <button
          type="button"
          onClick={onOpenWorkspace}
          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-400 hover:text-gray-200 hover:bg-white/5 rounded transition-colors"
        >
          <Folder className="size-4" />
          <span>打开 Workspace</span>
        </button>
        {onOpenHistory && (
          <button
            type="button"
            onClick={onOpenHistory}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-400 hover:text-gray-200 hover:bg-white/5 rounded transition-colors"
          >
            <History className="size-4" />
            <span>运行历史</span>
          </button>
        )}
      </div>
    </div>
  );
}
