import { Database, Clock, AlertCircle, ChevronDown, ChevronRight } from 'lucide-react';

interface MemoryPanelProps {
  content: string;
  mtime: string;
  loading: boolean;
  error: string | null;
  collapsed?: boolean;
  onToggle?: () => void;
}

export function MemoryPanel({ content, mtime, loading, error, collapsed, onToggle }: MemoryPanelProps) {
  return (
    <div className="h-full bg-[#1e1e1e] border-l border-gray-800 flex flex-col">
      <div className="px-4 py-3 border-b border-gray-800 bg-[#252526] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database className="size-4 text-blue-400" />
          <h2 className="text-sm font-semibold text-gray-300">Memory</h2>
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-500">
          <div className="flex items-center gap-1">
            <Clock className="size-3" />
            <span>{mtime || '-'}</span>
          </div>
          <button
            type="button"
            onClick={onToggle}
            className="flex items-center gap-1 rounded px-2 py-1 text-[11px] text-gray-400 hover:bg-white/5"
            aria-label={collapsed ? 'Expand memory panel' : 'Collapse memory panel'}
          >
            {collapsed ? <ChevronRight className="size-3" /> : <ChevronDown className="size-3" />}
            <span>{collapsed ? 'Expand' : 'Collapse'}</span>
          </button>
        </div>
      </div>

      {collapsed ? null : (
      <div className="flex-1 overflow-auto">
        {error ? (
          <div className="p-4 text-sm text-red-300 flex items-center gap-2">
            <AlertCircle className="size-4" />
            <span>{error}</span>
          </div>
        ) : null}
        {loading ? (
          <div className="p-4 text-sm text-gray-300">加载中...</div>
        ) : (
          <pre className="p-4 text-xs text-gray-300 font-mono leading-relaxed whitespace-pre-wrap">
            <code>{content || '(空)'}</code>
          </pre>
        )}
      </div>
      )}
    </div>
  );
}
