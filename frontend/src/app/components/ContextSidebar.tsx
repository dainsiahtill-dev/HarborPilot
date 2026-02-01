import { useState } from 'react';
import { MessageSquare, FileText, Brain, Database } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
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
        <div className="flex h-full glass-bubble border-l-0 overflow-hidden">
            {/* Tab Strip (Vertical Left) */}
            <div className="w-14 flex flex-col items-center py-6 gap-6 border-r border-white/5 bg-black/40 backdrop-blur-xl z-20">
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
                <AnimatePresence mode="wait">
                    {activeTab === 'dialogue' && (
                        <motion.div
                            key="dialogue"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            transition={{ duration: 0.2, ease: "easeOut" }}
                            className="absolute inset-0 flex flex-col"
                        >
                            <div className="flex-none p-3 border-b border-white/5 flex items-center justify-between bg-white/5 backdrop-blur-md">
                                <div className="flex items-center gap-2">
                                    <MessageSquare className="size-4 text-blue-400" />
                                    <span className="text-xs font-bold text-text-main uppercase tracking-widest">Dialogue</span>
                                </div>
                                <div className="text-[10px] text-text-dim px-2 py-0.5 rounded-full bg-black/30 border border-white/5">
                                    {live ? 'LIVE' : 'OFFLINE'}
                                </div>
                            </div>
                            <div className="flex-1 min-h-0 relative">
                                <DialoguePanel events={dialogueEvents} live={live} loading={dialogueLoading} />
                            </div>
                        </motion.div>
                    )}

                    {activeTab === 'memos' && (
                        <motion.div
                            key="memos"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            transition={{ duration: 0.2, ease: "easeOut" }}
                            className="absolute inset-0 flex flex-col"
                        >
                            <MemoPanel
                                items={memoItems}
                                selected={memoSelected}
                                content={memoContent}
                                mtime={memoMtime}
                                loading={memoLoading}
                                error={memoError}
                                onSelect={onSelectMemo}
                            />
                        </motion.div>
                    )}

                    {activeTab === 'memory' && settingsShowMemory && (
                        <motion.div
                            key="memory"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            transition={{ duration: 0.2, ease: "easeOut" }}
                            className="absolute inset-0 flex flex-col"
                        >
                            <div className="flex-none p-2 border-b border-white/5 flex items-center justify-between bg-white/5 backdrop-blur-md">
                                <div className="flex items-center gap-2">
                                    {showCognition ? <Brain className="size-4 text-purple-400" /> : <Database className="size-4 text-blue-400" />}
                                    <span className="text-xs font-bold text-text-main uppercase tracking-widest">Memory</span>
                                </div>
                                <div className="flex bg-black/30 p-0.5 rounded-lg border border-white/5">
                                    <button
                                        onClick={() => setShowCognition(true)}
                                        className={`px-2 py-1 text-[10px] rounded transition-all ${showCognition ? 'bg-purple-500/20 text-purple-300' : 'text-gray-500 hover:text-gray-300'}`}
                                    >
                                        Mind
                                    </button>
                                    <button
                                        onClick={() => setShowCognition(false)}
                                        className={`px-2 py-1 text-[10px] rounded transition-all ${!showCognition ? 'bg-blue-500/20 text-blue-300' : 'text-gray-500 hover:text-gray-300'}`}
                                    >
                                        Raw
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
                                    />
                                )}
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
}

function TabButton({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
    return (
        <button
            onClick={onClick}
            className={`group relative flex flex-col items-center justify-center p-3 rounded-2xl transition-all duration-500 ${active ? 'bg-white/10 text-accent shadow-[0_0_20px_rgba(139,92,246,0.3)] border border-white/10' : 'text-text-muted hover:text-white hover:bg-white/5'}`}
            title={label}
        >
            {active && (
                <motion.div
                    layoutId="activeTabIndicator"
                    className="absolute -left-1 w-1 h-8 bg-accent rounded-r shadow-glow"
                />
            )}
            <div className={`transition-all duration-500 ${active ? 'scale-110' : 'group-hover:scale-110 group-hover:drop-shadow-[0_0_8px_rgba(255,255,255,0.3)]'}`}>
                {icon}
            </div>
        </button>
    );
}

