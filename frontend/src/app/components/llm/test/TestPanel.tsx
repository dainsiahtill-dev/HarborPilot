import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import { Loader2, PlayCircle } from 'lucide-react';
import type { SimpleProvider } from '../types';
import type { TestEvent, TestEventType } from './types';
import { TerminalOutput } from './TerminalOutput';
import { TestPanelHeader } from './TestPanelHeader';
import { useTestStream } from './hooks/useTestStream';

interface TestPanelProps {
  provider: SimpleProvider;
  events?: TestEvent[]; // 静态事件数组（可选，用于兼容性）
  status?: 'idle' | 'running' | 'success' | 'failed';
  onClose: () => void;
  onCancel?: () => void;
  // 测试完成回调（包含结果）
  onTestComplete?: (result: { success: boolean; events: TestEvent[] }) => void;
  // 用于 SSE 流式测试的配置
  role?: string;
  apiKey?: string | null;
  testLevel?: string;
  evaluationMode?: string;
  suites?: string[];
  // 是否自动开始测试（默认 false，需要用户手动点击）
  autoStart?: boolean;
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
  events: externalEvents = [],
  status: externalStatus,
  onClose,
  onCancel: externalOnCancel,
  onTestComplete,
  role = 'connectivity',
  apiKey,
  testLevel = 'quick',
  evaluationMode = 'provider',
  suites = ['connectivity', 'response'],
  autoStart = false,
}: TestPanelProps) {
  // 内部事件状态 - 用于 SSE 流式输出
  const [events, setEvents] = useState<TestEvent[]>(externalEvents);
  const [internalStatus, setInternalStatus] = useState<'idle' | 'running' | 'success' | 'failed'>('idle');

  // Sync external events when they change (for external test control)
  useEffect(() => {
    if (externalEvents.length > 0) {
      setEvents(externalEvents);
    } else if (externalStatus === 'idle' && internalStatus === 'idle') {
      // Only reset if both are idle (new session)
      setEvents([]);
    }
  }, [externalEvents, externalStatus, internalStatus]);
  
  // 状态优先级：内部流式状态 > 外部控制状态
  // 当流式测试完成时，使用内部状态；否则使用外部状态
  const hasInternalResult = internalStatus === 'success' || internalStatus === 'failed';
  const status = hasInternalResult ? internalStatus : (externalStatus ?? internalStatus);
  const running = status === 'running';
  const statusLabel =
    status === 'idle'
      ? '准备就绪'
      : status === 'running'
        ? '测试中'
        : status === 'success'
          ? '成功'
          : '失败';
  
  // SSE 流式测试回调 - 使用 useCallback 保持稳定引用
  const handleEvent = useCallback((event: TestEvent) => {
    console.log('[TestPanel] handleEvent:', event);
    setEvents((prev) => [...prev, event]);
  }, []);
  
  const handleSuiteStart = useCallback((suite: string) => {
    console.log(`Starting suite: ${suite}`);
  }, []);
  
  const handleSuiteComplete = useCallback((suite: string, result: { ok: boolean }) => {
    console.log(`Suite ${suite}: ${result.ok ? 'PASS' : 'FAIL'}`);
  }, []);
  
  const handleComplete = useCallback(() => {
    setInternalStatus('success');
    onTestComplete?.({ success: true, events });
  }, [events, onTestComplete]);
  
  const handleError = useCallback(() => {
    setInternalStatus('failed');
    onTestComplete?.({ success: false, events });
  }, [events, onTestComplete]);
  
  // SSE 流式测试 Hook
  const { isStreaming, startStream, stopStream } = useTestStream({
    onEvent: handleEvent,
    onSuiteStart: handleSuiteStart,
    onSuiteComplete: handleSuiteComplete,
    onComplete: handleComplete,
    onError: handleError,
  });



  // 处理测试启动
  const handleRunTest = useCallback(() => {
    console.log('[TestPanel] handleRunTest called');
    // 清空之前的事件
    setEvents([]);
    setInternalStatus('running');
    
    // 🚀 立即添加启动事件，给用户即时反馈
    const now = new Date().toISOString();
    setEvents([
      {
        type: 'stdout',
        timestamp: now,
        content: `🚀 正在启动对 ${provider.name} 的测试...`,
      },
      {
        type: 'stdout',
        timestamp: now,
        content: `📡 正在连接到测试服务器...`,
      },
    ]);
    
    // 启动 SSE 流式测试（使用 useTestStream hook 处理所有事件）
    console.log('[TestPanel] Calling startStream');
    startStream({
      role,
      providerId: provider.id,
      model: provider.modelId || 'default',
      suites,
      testLevel,
      evaluationMode,
      apiKey,
    });
    
    // 注意：不调用 externalOnRunTest，避免双重请求
    // useTestStream 会通过 onEvent 回调更新 events 状态
  }, [provider, role, suites, testLevel, evaluationMode, apiKey, startStream]);

  // autoStart 控制是否自动开始测试
  // 当 autoStart 从 false 变为 true 时，自动触发测试
  useEffect(() => {
    if (autoStart && internalStatus === 'idle') {
      console.log('[TestPanel] autoStart triggered, starting test...');
      handleRunTest();
    }
  }, [autoStart, internalStatus, handleRunTest]);

  // 处理取消
  const handleCancel = useCallback(() => {
    stopStream();
    setInternalStatus('idle');
    externalOnCancel?.();
  }, [stopStream, externalOnCancel]);
  
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
                if (running) {
                  handleCancel();
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
              onClick={handleRunTest}
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
