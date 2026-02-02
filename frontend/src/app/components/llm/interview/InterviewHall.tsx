import { CheckCircle2, AlertTriangle, PlayCircle, ShieldCheck } from 'lucide-react';

export interface InterviewRoleSummary {
  id: 'pm' | 'director' | 'qa' | 'docs';
  label: string;
  description: string;
  requiresThinking: boolean;
  minConfidence: number;
  thinkingConfidence?: number | null;
  thinkingSupported?: boolean | null;
  candidate?: {
    providerId?: string;
    providerName?: string;
    model?: string;
  };
  readiness?: {
    ready?: boolean;
    grade?: string;
  };
}

export interface InterviewCandidateSummary {
  id: string;
  roleLabel: string;
  providerName: string;
  model: string;
  ready?: boolean;
  thinkingSupported?: boolean | null;
  thinkingConfidence?: number | null;
}

interface InterviewHallProps {
  roles: InterviewRoleSummary[];
  candidates: InterviewCandidateSummary[];
  selectedRole: 'pm' | 'director' | 'qa' | 'docs';
  onSelectRole: (role: 'pm' | 'director' | 'qa' | 'docs') => void;
  onStartInterview: () => void;
  onRunReadiness?: () => void;
  disabledReason?: string | null;
  running?: boolean;
}

const ROLE_BADGES: Record<string, string> = {
  pm: 'bg-cyan-500/20 text-cyan-200 border-cyan-500/30',
  director: 'bg-emerald-500/20 text-emerald-200 border-emerald-500/30',
  qa: 'bg-blue-500/20 text-blue-200 border-blue-500/30',
  docs: 'bg-amber-500/20 text-amber-200 border-amber-500/30'
};

export function InterviewHall({
  roles,
  candidates,
  selectedRole,
  onSelectRole,
  onStartInterview,
  onRunReadiness,
  disabledReason,
  running
}: InterviewHallProps) {
  const activeRole = roles.find(role => role.id === selectedRole);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs text-text-dim uppercase tracking-wide">LLM Interview Center</div>
          <h3 className="text-lg font-semibold text-text-main">面试大厅</h3>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-text-dim">
          <ShieldCheck className="size-4 text-emerald-300" />
          Core roles require thinking-capable models.
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_1fr] gap-6">
        <div className="space-y-4">
          <div className="text-xs font-semibold text-text-main uppercase tracking-wide">🎯 面试岗位</div>
          {roles.map(role => {
            const isActive = role.id === selectedRole;
            const badge = ROLE_BADGES[role.id] || 'bg-white/10 text-text-main border-white/20';
            return (
              <button
                key={role.id}
                onClick={() => onSelectRole(role.id)}
                className={`w-full text-left rounded-xl border p-4 transition-all ${
                  isActive
                    ? 'border-cyan-400/60 bg-cyan-500/10'
                    : 'border-white/10 bg-white/5 hover:border-white/20'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-1 text-[10px] uppercase font-semibold rounded border ${badge}`}>
                      {role.label}
                    </span>
                    {role.readiness?.ready ? (
                      <CheckCircle2 className="size-4 text-emerald-400" />
                    ) : (
                      <AlertTriangle className="size-4 text-amber-300" />
                    )}
                  </div>
                  <div className="text-[10px] text-text-dim uppercase tracking-wide">
                    {role.requiresThinking ? 'Thinking Required' : 'Thinking Optional'}
                  </div>
                </div>
                <div className="mt-2 text-xs text-text-dim">{role.description}</div>
                <div className="mt-3 text-[11px] text-text-main">
                  Candidate: {role.candidate?.providerName || 'Unassigned'} {role.candidate?.model ? `• ${role.candidate.model}` : ''}
                </div>
              </button>
            );
          })}
        </div>

        <div className="space-y-4">
          <div className="text-xs font-semibold text-text-main uppercase tracking-wide">👥 应聘者列表</div>
          <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
            {candidates.length === 0 ? (
              <div className="text-xs text-text-dim">No configured models yet.</div>
            ) : (
              candidates.map(candidate => (
                <div key={candidate.id} className="flex items-center justify-between text-xs">
                  <div>
                    <div className="text-text-main font-semibold">{candidate.providerName}</div>
                    <div className="text-text-dim">{candidate.model}</div>
                  </div>
                  <div className="text-[10px] text-text-dim text-right">
                    <div>{candidate.roleLabel}</div>
                    <div>
                      Thinking {candidate.thinkingSupported ? 'OK' : '—'}{' '}
                      {candidate.thinkingConfidence !== null && candidate.thinkingConfidence !== undefined
                        ? `${Math.round(candidate.thinkingConfidence * 100)}%`
                        : ''}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="rounded-xl border border-white/10 bg-black/30 p-4 space-y-3">
            <div className="text-xs font-semibold text-text-main uppercase tracking-wide">🚀 开始面试</div>
            <div className="text-xs text-text-dim">
              {activeRole?.requiresThinking
                ? `核心岗位要求 thinking 模型（最低 ${Math.round(activeRole.minConfidence * 100)}% 置信度）。`
                : '辅助岗位可使用高效模型，thinking 能力为加分项。'}
            </div>
            <div className="text-[11px] text-text-dim">
              Thinking 检测：{activeRole?.thinkingConfidence !== null && activeRole?.thinkingConfidence !== undefined
                ? `${Math.round(activeRole.thinkingConfidence * 100)}%`
                : '未检测'}
            </div>
            {disabledReason ? (
              <div className="text-[11px] text-red-200 bg-red-500/10 border border-red-500/20 rounded p-2">
                {disabledReason}
              </div>
            ) : null}
            <div className="flex items-center gap-2">
              <button
                onClick={onStartInterview}
                disabled={!!disabledReason || running}
                className="px-3 py-2 text-[11px] font-semibold bg-emerald-500/80 hover:bg-emerald-500 text-white rounded transition-colors disabled:opacity-60 flex items-center gap-1"
              >
                <PlayCircle className="size-3" />
                {running ? 'Interviewing...' : 'Start Interview'}
              </button>
              {onRunReadiness ? (
                <button
                  onClick={onRunReadiness}
                  className="px-3 py-2 text-[11px] border border-white/10 rounded hover:border-cyan-400/40"
                >
                  Quick Screening
                </button>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
