import { Loader2, PlayCircle } from 'lucide-react';
import type { SimpleProvider } from '../types';
import type { TestEvent } from './types';
import { TerminalOutput } from './TerminalOutput';
import { TestPanelHeader } from './TestPanelHeader';

interface TestPanelProps {
  provider: SimpleProvider;
  events: TestEvent[];
  status: 'idle' | 'running' | 'success' | 'failed';
  onClose: () => void;
  onRunTest: () => void;
  onCancel?: () => void;
}

export function TestPanel({
  provider,
  events,
  status,
  onClose,
  onRunTest,
  onCancel,
}: TestPanelProps) {
  const running = status === 'running';
  const statusLabel =
    status === 'idle'
      ? '准备就绪'
      : status === 'running'
        ? '测试中'
        : status === 'success'
          ? '成功'
          : '失败';
  return (
    <div className="relative bg-black/30 bg-gradient-to-br from-cyan-500/10 via-purple-500/10 to-pink-500/10 rounded-xl border border-cyan-400/30 shadow-[0_0_20px_rgba(34,211,238,0.18),0_0_40px_rgba(168,85,247,0.12)] backdrop-blur-xl h-fit overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/60 via-fuchsia-400/50 to-pink-400/60" />
      <TestPanelHeader
        provider={provider}
        status={status}
        onClose={onClose}
        running={running}
      />

      <div className="p-4 space-y-3">
        <div className="grid grid-cols-3 gap-3 text-[10px] text-text-dim">
          <div className="rounded border border-white/10 bg-black/20 px-2 py-1">
            状态: <span className="text-text-main">{statusLabel}</span>
          </div>
          <div className="rounded border border-white/10 bg-black/20 px-2 py-1">
            提供商: <span className="text-text-main">{provider.name}</span>
          </div>
          <div className="rounded border border-white/10 bg-black/20 px-2 py-1">
            模型: <span className="text-text-main">{provider.modelId || 'default'}</span>
          </div>
        </div>

        <TerminalOutput events={events} />
      </div>

      <div className="p-4 border-t border-white/10 flex items-center gap-2">
        <button
          type="button"
          onClick={() => {
            if (running && onCancel) {
              onCancel();
            } else {
              onClose();
            }
          }}
          disabled={false}
          className="px-4 py-2 text-xs border border-white/10 rounded hover:border-red-400/40"
        >
          {running ? '取消测试' : '取消'}
        </button>
        <button
          type="button"
          onClick={onRunTest}
          disabled={running}
          className="px-4 py-2 text-xs bg-emerald-500/80 hover:bg-emerald-500 text-white rounded disabled:opacity-60 flex items-center gap-1"
        >
          {running ? <Loader2 className="size-3 animate-spin" /> : <PlayCircle className="size-3" />}
          {running ? '测试中...' : '测试'}
        </button>
      </div>
    </div>
  );
}
