import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import { Loader2, PlayCircle } from 'lucide-react';
import type { SimpleProvider } from '../types';
import type { TestEvent, TestEventType } from './types';
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

const EVENT_PREFIX: Record<TestEventType, string> = {
  command: '$',
  stdout: '>',
  stderr: '!',
  response: '<',
  result: '✓',
  error: '✗'
};

const formatEventLine = (event: TestEvent) => {
  const prefix = EVENT_PREFIX[event.type] || '>';
  const time = new Date(event.timestamp).toLocaleTimeString();
  const details = event.details ? ` ${JSON.stringify(event.details)}` : '';
  return `[${time}] ${prefix} ${event.content}${details}`;
};

const formatEvents = (events: TestEvent[]) => {
  if (!events.length) return '';
  return events.map(formatEventLine).join('\n');
};

const sanitizeFilename = (value: string) => (value || 'session').replace(/[^A-Za-z0-9_.-]+/g, '_');

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
  const [collapsed, setCollapsed] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const dragState = useRef({ active: false, startX: 0, startY: 0, originX: 0, originY: 0 });

  const handlePointerMove = useCallback((event: PointerEvent) => {
    if (!dragState.current.active) return;
    const deltaX = event.clientX - dragState.current.startX;
    const deltaY = event.clientY - dragState.current.startY;
    setPosition({
      x: dragState.current.originX + deltaX,
      y: dragState.current.originY + deltaY
    });
  }, []);

  const handlePointerUp = useCallback(() => {
    if (!dragState.current.active) return;
    dragState.current.active = false;
    setDragging(false);
    window.removeEventListener('pointermove', handlePointerMove);
    window.removeEventListener('pointerup', handlePointerUp);
  }, [handlePointerMove]);

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    const target = event.target as HTMLElement;
    if (target.closest('button')) return;
    event.preventDefault();
    dragState.current = {
      active: true,
      startX: event.clientX,
      startY: event.clientY,
      originX: position.x,
      originY: position.y
    };
    setDragging(true);
    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
  };

  useEffect(() => {
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };
  }, [handlePointerMove, handlePointerUp]);

  const logText = useMemo(() => formatEvents(events), [events]);

  const handleCopyLogs = async () => {
    if (!logText) return;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(logText);
        return;
      }
    } catch {
      // fallback below
    }
    try {
      const textarea = document.createElement('textarea');
      textarea.value = logText;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
    } catch {
      // ignore copy failure
    }
  };

  const handleExportLogs = () => {
    if (!logText) return;
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `${sanitizeFilename(provider.name)}-${stamp}.log`;
    const blob = new Blob([logText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  };

  return (
    <div
      className={`relative bg-black/30 bg-gradient-to-br from-cyan-500/10 via-purple-500/10 to-pink-500/10 rounded-xl border border-cyan-400/30 shadow-[0_0_20px_rgba(34,211,238,0.18),0_0_40px_rgba(168,85,247,0.12)] backdrop-blur-xl h-fit overflow-hidden transition-all ${
        collapsed ? 'max-w-[240px]' : 'w-full'
      }`}
      style={{ transform: `translate(${position.x}px, ${position.y}px)` }}
    >
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/60 via-fuchsia-400/50 to-pink-400/60" />
      <div
        onPointerDown={handlePointerDown}
        className={`select-none ${dragging ? 'cursor-grabbing' : 'cursor-grab'}`}
        style={{ touchAction: 'none' }}
      >
        <TestPanelHeader
          provider={provider}
          status={status}
          onClose={onClose}
          running={running}
          collapsed={collapsed}
          onToggleCollapse={() => setCollapsed((prev) => !prev)}
          onCopyLogs={handleCopyLogs}
          onExportLogs={handleExportLogs}
        />
      </div>

      {!collapsed ? (
        <>
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
        </>
      ) : null}
    </div>
  );
}
