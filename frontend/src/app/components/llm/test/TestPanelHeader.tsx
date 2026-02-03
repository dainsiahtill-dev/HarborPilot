import { X, Loader2 } from 'lucide-react';
import type { SimpleProvider } from '../types';

interface TestPanelHeaderProps {
  provider: SimpleProvider;
  status: 'idle' | 'running' | 'success' | 'failed';
  onClose: () => void;
  running?: boolean;
}

const STATUS_TEXT: Record<TestPanelHeaderProps['status'], string> = {
  idle: '准备就绪',
  running: '测试中',
  success: '成功',
  failed: '失败'
};

const STATUS_BADGES: Record<TestPanelHeaderProps['status'], string> = {
  idle: 'bg-gray-500/20 text-gray-300 border-gray-500/30',
  running: 'bg-cyan-500/20 text-cyan-200 border-cyan-500/30',
  success: 'bg-emerald-500/20 text-emerald-200 border-emerald-500/30',
  failed: 'bg-red-500/20 text-red-200 border-red-500/30'
};

export function TestPanelHeader({
  provider,
  status,
  onClose,
  running
}: TestPanelHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4 p-4 border-b border-cyan-500/20 bg-black/40">
      <div>
        <div className="text-sm font-semibold text-text-main flex items-center gap-2">
          🖥️ Testing: {provider.name}
          <span className={`text-[9px] uppercase tracking-wider px-2 py-0.5 rounded border ${STATUS_BADGES[status]}`}>
            {STATUS_TEXT[status]}
          </span>
        </div>
        <div className="text-[10px] text-text-dim mt-1">
          Provider: {provider.name} · Model: {provider.modelId || 'default'}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onClose}
          disabled={running}
          className="p-1.5 rounded border border-white/10 hover:border-accent/40 disabled:opacity-50"
        >
          {running ? <Loader2 className="size-3 animate-spin" /> : <X className="size-3" />}
        </button>
      </div>
    </div>
  );
}


