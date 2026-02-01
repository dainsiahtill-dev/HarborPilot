import { useState } from 'react';
import { MessageSquare, FileText, Brain, Database, ChevronRight } from 'lucide-react';
import { DialoguePanel, DialogueEvent } from '@/app/components/DialoguePanel';
import { MemoPanel, MemoItem } from '@/app/components/MemoPanel';
import { MemoryPanel } from '@/app/components/MemoryPanel';
import { CognitionPanel } from '@/app/components/CognitionPanel';

export type ContextTab = 'dialogue' | 'memos' | 'memory';

interface ContextSidebarProps {
    // Dialogue Props
    dialogueEvents: DialogueEvent[];
    live: boolean;
    dialogueLoading: boolean;

    // Memo Props
    memoItems: MemoItem[];
    memoSelected: MemoItem | null;
    memoContent: string;
    memoMtime: string;
    memoLoading: boolean;
    memoError: string | null;
    onSelectMemo: (item: MemoItem) => void;

    // Memory Props
    memoryContent: string;
    memoryMtime: string;
    memoryLoading: boolean;
    memoryError: string | null;
    showCognition: boolean;
    setShowCognition: (show: boolean) => void;
    settingsShowMemory: boolean;
}

export function ContextSidebar({
    dialogueEvents,
    live,
    dialogueLoading,
    memoItems,
    memoSelected,
    memoContent,
    memoMtime,
    memoLoading,
    memoError,
    onSelectMemo,
    memoryContent,
    memoryMtime,
    memoryLoading,
    memoryError,
    showCognition,
    setShowCognition,
    settingsShowMemory
}: ContextSidebarProps) {
    const [activeTab, setActiveTab] = useState<ContextTab>('dialogue');

    return (
        <div className="flex h-full bg-bg-panel/30 backdrop-blur-md border-l border-white/10 overflow-hidden">
            {/* Tab Strip (Vertical Left) */}
            <div className="w-12 flex flex-col items-center py-4 gap-4 border-r border-white/5 bg-black/20">
                <TabButton
                    active={activeTab === 'dialogue'}
                    onClick={() => setActiveTab('dialogue')}
                    icon={<MessageSquare className="size-5" />}
                    label="Chat"
                />
                <TabButton
                    active={activeTab === 'memos'}
                    onClick={() => setActiveTab('memos')}
                    icon={<FileText className="size-5" />}
                    label="Memos"
                />
                {settingsShowMemory && (
                    <TabButton
                        active={activeTab === 'memory'}
                        onClick={() => setActiveTab('memory')}
                        icon={showCognition ? <Brain className="size-5" /> : <Database className="size-5" />}
                        label="Memory"
                    />
                )}
            </div>

            {/* Content Area */}
            <div className="flex-1 min-w-0 flex flex-col relative bg-gradient-to-br from-transparent to-black/20">

                {/* Dialogue View */}
                <div className={`absolute inset-0 flex flex-col transition-opacity duration-300 ${activeTab === 'dialogue' ? 'opacity-100 z-10 pointer-events-auto' : 'opacity-0 z-0 pointer-events-none'}`}>
                    <div className="flex-none p-3 border-b border-white/5 flex items-center justify-between bg-white/5">
                        <div className="flex items-center gap-2">
                            <MessageSquare className="size-4 text-blue-400" />
                            <span className="text-xs font-semibold text-text-main">Mission Dialogue</span>
                        </div>
                        <div className="text-[10px] text-text-dim px-2 py-0.5 rounded-full bg-black/30 border border-white/5">
                            {live ? 'LIVE' : 'OFFLINE'}
                        </div>
                    </div>
                    <div className="flex-1 min-h-0 relative">
                        <DialoguePanel events={dialogueEvents} live={live} loading={dialogueLoading} />
                    </div>
                </div>

                {/* Memo View */}
                <div className={`absolute inset-0 flex flex-col transition-opacity duration-300 ${activeTab === 'memos' ? 'opacity-100 z-10 pointer-events-auto' : 'opacity-0 z-0 pointer-events-none'}`}>
                    <MemoPanel
                        items={memoItems}
                        selected={memoSelected}
                        content={memoContent}
                        mtime={memoMtime}
                        loading={memoLoading}
                        error={memoError}
                        onSelect={onSelectMemo}
                    // Remove collapse/toggle props as we are now full panel
                    />
                </div>

                {/* Memory View */}
                {settingsShowMemory && (
                    <div className={`absolute inset-0 flex flex-col transition-opacity duration-300 ${activeTab === 'memory' ? 'opacity-100 z-10 pointer-events-auto' : 'opacity-0 z-0 pointer-events-none'}`}>
                        <div className="flex-none p-2 border-b border-white/5 flex items-center justify-between bg-white/5">
                            <div className="flex items-center gap-2">
                                {showCognition ? <Brain className="size-4 text-purple-400" /> : <Database className="size-4 text-blue-400" />}
                                <span className="text-xs font-semibold text-text-main">Core Memory</span>
                            </div>
                            <div className="flex bg-black/30 p-0.5 rounded-lg border border-white/5">
                                <button
                                    onClick={() => setShowCognition(true)}
                                    className={`px-2 py-1 text-[10px] rounded transition-all ${showCognition ? 'bg-purple-500/20 text-purple-300' : 'text-gray-500 hover:text-gray-300'}`}
                                >
                                    Glass Mind
                                </button>
                                <button
                                    onClick={() => setShowCognition(false)}
                                    className={`px-2 py-1 text-[10px] rounded transition-all ${!showCognition ? 'bg-blue-500/20 text-blue-300' : 'text-gray-500 hover:text-gray-300'}`}
                                >
                                    Raw Data
                                </button>
                            </div>
                        </div>
                        <div className="flex-1 min-h-0 relative overflow-hidden">
                            {showCognition ? (
                                <CognitionPanel events={dialogueEvents} loading={!live} />
                            ) : (
                                <MemoryPanel
                                    content={memoryContent}
                                    mtime={memoryMtime}
                                    loading={memoryLoading}
                                    error={memoryError}
                                // Remove collapse props
                                />
                            )}
                        </div>
                    </div>
                )}

            </div>
        </div>
    );
}

function TabButton({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
    return (
        <button
            onClick={onClick}
            className={`group relative flex flex-col items-center justify-center p-2 rounded-xl transition-all duration-300 ${active ? 'bg-white/10 text-accent shadow-[0_0_15px_rgba(139,92,246,0.2)]' : 'text-text-muted hover:text-white hover:bg-white/5'}`}
            title={label}
        >
            {active && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-accent rounded-r shadow-glow" />
            )}
            <div className={`transition-transform duration-300 ${active ? 'scale-110' : 'group-hover:scale-110'}`}>
                {icon}
            </div>
        </button>
    );
}
