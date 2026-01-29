import { Database, Clock, AlertCircle } from 'lucide-react';

interface MemoryPanelProps {
  content: string;
  mtime: string;
  loading: boolean;
  error: string | null;
}

export function MemoryPanel({ content, mtime, loading, error }: MemoryPanelProps) {
  const displayContent = content || (loading ? '' : '// 暂无 memory 数据');

  return (
    <div className="h-full bg-[#1e1e1e] border-l border-gray-800 flex flex-col">
      <div className="px-4 py-3 border-b border-gray-800 bg-[#252526] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database className="size-4 text-blue-400" />
          <h2 className="text-sm font-semibold text-gray-300">Memory</h2>
        </div>
        <div className="flex items-center gap-1 text-xs text-gray-500">
          <Clock className="size-3" />
          <span>{mtime || '-'}</span>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {error ? (
          <div className="p-4 text-sm text-red-300 flex items-center gap-2">
            <AlertCircle className="size-4" />
            <span>{error}</span>
          </div>
        ) : null}
        <pre className="p-4 text-xs text-gray-300 font-mono leading-relaxed whitespace-pre-wrap">
          <code>{displayContent}</code>
        </pre>
      </div>
    </div>
  );
}
