import { memo } from 'react';
import { ArrowRight } from 'lucide-react';

interface CurrentTaskCardProps {
    currentSummary: string;
    lastTaskId?: string;
}

export const CurrentTaskCard = memo(function CurrentTaskCard({ currentSummary, lastTaskId }: CurrentTaskCardProps) {
    return (
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur-md hover:border-accent/30 transition-all">
            <div className="flex items-center justify-between gap-2">
                <div className="text-xs font-semibold uppercase tracking-wide text-text-muted">当前 Director 任务</div>
                <ArrowRight className="size-4 text-accent animate-pulse" />
            </div>
            {currentSummary ? (
                <div className="mt-3 flex items-start gap-3">
                    <div className="mt-1 flex size-8 items-center justify-center rounded-full bg-accent/20 text-accent shadow-[0_0_10px_rgba(124,58,237,0.3)]">
                        <ArrowRight className="size-4" />
                    </div>
                    <div className="min-w-0">
                        <div className="text-sm font-semibold text-text-main">{currentSummary}</div>
                        <div className="mt-1 text-xs text-text-dim font-mono">
                            {lastTaskId ? <span>ID: {lastTaskId}</span> : <span>等待 PM 分配任务</span>}
                        </div>
                    </div>
                </div>
            ) : (
                <div className="mt-3 text-sm text-text-dim">暂无当前任务信息</div>
            )}
        </div>
    );
});
