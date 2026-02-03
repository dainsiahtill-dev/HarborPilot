import { useEffect, useRef, useState } from 'react';
import type { TestEvent, TestEventType } from './types';

const EVENT_STYLES: Record<TestEventType, { prefix: string; className: string }> = {
  command: { prefix: '$', className: 'text-blue-400' },
  stdout: { prefix: '>', className: 'text-green-400' },
  stderr: { prefix: '!', className: 'text-yellow-400' },
  response: { prefix: '<', className: 'text-cyan-400' },
  result: { prefix: '✓', className: 'text-emerald-400' },
  error: { prefix: '✗', className: 'text-red-400' }
};

interface TerminalOutputProps {
  events: TestEvent[];
  placeholder?: string;
}

export function TerminalOutput({ events, placeholder }: TerminalOutputProps) {
  const outputRef = useRef<HTMLDivElement | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    const el = outputRef.current;
    if (!el || !autoScroll) return;
    el.scrollTop = el.scrollHeight;
  }, [events, autoScroll]);

  useEffect(() => {
    const el = outputRef.current;
    if (!el) return;
    const onScroll = () => {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
      setAutoScroll(nearBottom);
    };
    el.addEventListener('scroll', onScroll);
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-[10px] text-text-dim">
        <span>终端输出</span>
        <span className="text-[9px]">{autoScroll ? '自动滚动' : '已暂停滚动'}</span>
      </div>
      <div
        ref={outputRef}
        className="bg-black/70 text-green-200 font-mono text-[11px] p-3 rounded-lg border border-white/10 h-80 overflow-y-auto"
      >
        {events.length === 0 ? (
          <div className="text-gray-500">
            {placeholder || '$ 准备就绪，点击"测试"按钮开始...'}
          </div>
        ) : (
          events.map((event, index) => {
            const style = EVENT_STYLES[event.type];
            return (
              <div key={`${event.timestamp}-${index}`} className="mb-1 whitespace-pre-wrap break-words">
                <span className="text-gray-500">[{new Date(event.timestamp).toLocaleTimeString()}]</span>{' '}
                <span className={style.className}>
                  {style.prefix} {event.content}
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
