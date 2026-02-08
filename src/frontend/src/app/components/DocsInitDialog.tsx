import { useEffect, useMemo, useState } from 'react';
import { RiAiGenerate2 } from 'react-icons/ri';
import { apiFetch } from '@/api';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/app/components/ui/dialog';
import { Button } from '@/app/components/ui/button';
import { ScrollArea } from '@/app/components/ui/scroll-area';

export interface DocsInitFile {
  path: string;
  content: string;
  exists?: boolean;
}

export interface DocsInitPreview {
  mode: string;
  target_root: string;
  docs_exists: boolean;
  files: DocsInitFile[];
  project?: Record<string, unknown>;
}

export interface WorkspaceStatus {
  status: string;
  reason?: string;
  actions?: string[];
  workspace_path?: string;
  timestamp?: string;
}

interface DocsInitDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workspace?: string;
  workspaceStatus?: WorkspaceStatus | null;
  docsPresent?: boolean;
  onApplied?: () => void;
}

const MODE_OPTIONS = [
  {
    id: 'minimal',
    title: 'Minimal template',
    description: 'Generate a small docs set with your inputs.',
  },
  {
    id: 'import_readme',
    title: 'Import README',
    description: 'Use README title as a starting hint if present.',
  },
  {
    id: 'ai',
    title: 'AI polish (optional)',
    description: 'Polish text if available; falls back to minimal.',
  },
];

function buildAutoFill(goalText: string) {
  const goal = (goalText || '').trim();
  const lowered = goal.toLowerCase();
  const isNodeServer =
    lowered.includes('node') ||
    lowered.includes('nodejs') ||
    lowered.includes('node.js') ||
    lowered.includes('http server') ||
    lowered.includes('file server') ||
    lowered.includes('服务器');

  if (isNodeServer) {
    return {
      inScope: ['提供静态文件服务（可配置目录）', '基础 HTTP 日志', '启动/停止说明'].join('\n'),
      outOfScope: ['认证/授权', 'HTTPS/TLS 配置', '数据库接入'].join('\n'),
      constraints: ['优先使用 Node 内置 http 模块', '配置尽量简化'].join('\n'),
      definitionOfDone: ['npm test（如有）', '手动检查：GET / 返回 200', 'Lint 通过'].join('\n'),
      backlog: ['支持目录列表开关', '添加基础错误页', '支持端口环境变量'].join('\n'),
    };
  }

  return {
    inScope: ['明确核心用户路径', '交付最小可用功能'].join('\n'),
    outOfScope: ['非必要的第三方集成', '高级优化'].join('\n'),
    constraints: ['保持改动小', '优先使用现有工具链'].join('\n'),
    definitionOfDone: ['冒烟测试通过', 'Docs 已更新'].join('\n'),
    backlog: ['收集反馈', '补齐边界场景'].join('\n'),
  };
}

export function DocsInitDialog({
  open,
  onOpenChange,
  workspace,
  workspaceStatus,
  docsPresent,
  onApplied,
}: DocsInitDialogProps) {
  const [step, setStep] = useState(1);
  const [mode, setMode] = useState('minimal');
  const [goal, setGoal] = useState('');
  const [inScope, setInScope] = useState('');
  const [outOfScope, setOutOfScope] = useState('');
  const [constraints, setConstraints] = useState('');
  const [definitionOfDone, setDefinitionOfDone] = useState('');
  const [backlog, setBacklog] = useState('');
  const [preview, setPreview] = useState<DocsInitPreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [applying, setApplying] = useState(false);
  const [aiSuggesting, setAiSuggesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const docsMissing = useMemo(() => {
    if (docsPresent === false) return true;
    return workspaceStatus?.status === 'NEEDS_DOCS_INIT';
  }, [docsPresent, workspaceStatus?.status]);

  useEffect(() => {
    if (!open) return;
    setStep(1);
    setMode('minimal');
    setGoal('');
    setInScope('');
    setOutOfScope('');
    setConstraints('');
    setDefinitionOfDone('');
    setBacklog('');
    setPreview(null);
    setError(null);
    setLoadingPreview(false);
    setApplying(false);
    setAiSuggesting(false);
  }, [open, workspace]);

  const buildPreview = async () => {
    setLoadingPreview(true);
    setError(null);
    try {
      const res = await apiFetch('/docs/init/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode,
          goal,
          in_scope: inScope,
          out_of_scope: outOfScope,
          constraints,
          definition_of_done: definitionOfDone,
          backlog,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail?.detail || 'Failed to build preview.');
      }
      const data = (await res.json()) as DocsInitPreview & { ok?: boolean };
      setPreview(data);
      setStep(3);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to build preview.');
    } finally {
      setLoadingPreview(false);
    }
  };

  const applyDocs = async () => {
    if (!preview) return;
    setApplying(true);
    setError(null);
    try {
      const res = await apiFetch('/docs/init/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: preview.mode || mode,
          target_root: preview.target_root,
          files: preview.files.map((file) => ({
            path: file.path,
            content: file.content,
          })),
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail?.detail || 'Failed to write docs.');
      }
      toast.success('Docs initialized');
      onApplied?.();
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to write docs.');
    } finally {
      setApplying(false);
    }
  };

  const updatePreviewFile = (index: number, content: string) => {
    setPreview((prev) => {
      if (!prev) return prev;
      const nextFiles = [...prev.files];
      nextFiles[index] = { ...nextFiles[index], content };
      return { ...prev, files: nextFiles };
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl bg-[#1f2125] border border-emerald-500/30 text-gray-200">
        <DialogHeader>
          <DialogTitle className="text-emerald-200">Docs onboarding</DialogTitle>
          <DialogDescription className="text-gray-400">
            {docsMissing
              ? 'Your workspace is missing docs/. Generate the minimal doc set to continue.'
              : 'Generate or refresh docs. This wizard only writes under docs/.'}
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center justify-between text-xs text-gray-400">
          <span>Step {step} / 3</span>
          <span>{workspace ? `Workspace: ${workspace}` : 'Workspace not set'}</span>
        </div>

        {error ? (
          <div className="rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">
            {error}
          </div>
        ) : null}

        {step === 1 ? (
          <div className="grid gap-3">
            {MODE_OPTIONS.map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => setMode(option.id)}
                className={`rounded border px-4 py-3 text-left transition-colors ${
                  mode === option.id
                    ? 'border-emerald-500/60 bg-emerald-500/10'
                    : 'border-gray-700 bg-[#14161a] hover:border-gray-500'
                }`}
              >
                <div className="text-sm font-semibold text-gray-100">{option.title}</div>
                <div className="text-xs text-gray-400 mt-1">{option.description}</div>
              </button>
            ))}
          </div>
        ) : null}

        {step === 2 ? (
          <ScrollArea className="h-[50vh] rounded border border-gray-800 bg-[#14161a]">
            <div className="grid gap-4 p-4 text-sm">
              <label className="grid gap-2">
                <span className="text-gray-300">Goal</span>
                <div className="flex items-center gap-2">
                  <input
                    value={goal}
                    onChange={(event) => setGoal(event.target.value)}
                    className="flex-1 rounded border border-gray-700 bg-[#0f1115] px-3 py-2 text-sm text-gray-200"
                    placeholder="One-line goal"
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={async () => {
                      if (mode === 'ai') {
                        setAiSuggesting(true);
                        setError(null);
                        try {
                          const res = await apiFetch('/docs/init/suggest', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                              goal,
                              in_scope: inScope,
                              out_of_scope: outOfScope,
                              constraints,
                              definition_of_done: definitionOfDone,
                              backlog,
                            }),
                          });
                          if (!res.ok) {
                            const detail = await res.json().catch(() => ({}));
                            throw new Error(detail?.detail || 'AI suggestion failed.');
                          }
                          const data = (await res.json()) as {
                            fields?: Record<string, string>;
                          };
                          const fields = data.fields || {};
                          setGoal(fields.goal ?? goal);
                          setInScope(fields.in_scope ?? inScope);
                          setOutOfScope(fields.out_of_scope ?? outOfScope);
                          setConstraints(fields.constraints ?? constraints);
                          setDefinitionOfDone(fields.definition_of_done ?? definitionOfDone);
                          setBacklog(fields.backlog ?? backlog);
                          return;
                        } catch (err) {
                          toast.error(err instanceof Error ? err.message : 'AI suggestion failed.');
                        } finally {
                          setAiSuggesting(false);
                        }
                      }
                      const auto = buildAutoFill(goal);
                      setInScope(auto.inScope);
                      setOutOfScope(auto.outOfScope);
                      setConstraints(auto.constraints);
                      setDefinitionOfDone(auto.definitionOfDone);
                      setBacklog(auto.backlog);
                    }}
                  >
                    <span className="flex items-center gap-1.5">
                      <RiAiGenerate2 className="size-4" />
                      {aiSuggesting ? 'Generating...' : 'Generate'}
                    </span>
                  </Button>
                </div>
              </label>
              <label className="grid gap-2">
                <span className="text-gray-300">In Scope</span>
                <textarea
                  value={inScope}
                  onChange={(event) => setInScope(event.target.value)}
                  className="min-h-[90px] rounded border border-gray-700 bg-[#0f1115] px-3 py-2 text-sm text-gray-200"
                  placeholder="One item per line"
                />
              </label>
              <label className="grid gap-2">
                <span className="text-gray-300">Out of Scope</span>
                <textarea
                  value={outOfScope}
                  onChange={(event) => setOutOfScope(event.target.value)}
                  className="min-h-[90px] rounded border border-gray-700 bg-[#0f1115] px-3 py-2 text-sm text-gray-200"
                  placeholder="One item per line"
                />
              </label>
              <label className="grid gap-2">
                <span className="text-gray-300">Constraints</span>
                <textarea
                  value={constraints}
                  onChange={(event) => setConstraints(event.target.value)}
                  className="min-h-[90px] rounded border border-gray-700 bg-[#0f1115] px-3 py-2 text-sm text-gray-200"
                  placeholder="3-5 lines"
                />
              </label>
              <label className="grid gap-2">
                <span className="text-gray-300">Definition of Done</span>
                <textarea
                  value={definitionOfDone}
                  onChange={(event) => setDefinitionOfDone(event.target.value)}
                  className="min-h-[90px] rounded border border-gray-700 bg-[#0f1115] px-3 py-2 text-sm text-gray-200"
                  placeholder="QA commands or acceptance rules"
                />
              </label>
              <label className="grid gap-2">
                <span className="text-gray-300">Backlog (optional)</span>
                <textarea
                  value={backlog}
                  onChange={(event) => setBacklog(event.target.value)}
                  className="min-h-[90px] rounded border border-gray-700 bg-[#0f1115] px-3 py-2 text-sm text-gray-200"
                  placeholder="Initial backlog items"
                />
              </label>
            </div>
          </ScrollArea>
        ) : null}

        {step === 3 ? (
          <div className="grid gap-3">
            <div className="rounded border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100">
              <div>Target root: {preview?.target_root || 'docs'}</div>
              <div>Writes only under docs/. Apply to create files.</div>
            </div>
            <ScrollArea className="h-[50vh] rounded border border-gray-800 bg-[#14161a]">
              <div className="grid gap-4 p-4">
                {preview?.files.map((file, index) => (
                  <div key={file.path} className="rounded border border-gray-700 bg-[#0f1115]">
                    <div className="flex items-center justify-between border-b border-gray-800 px-3 py-2 text-xs text-gray-400">
                      <span>{file.path}</span>
                      {file.exists ? <span className="text-amber-300">exists</span> : <span>new</span>}
                    </div>
                    <textarea
                      value={file.content}
                      onChange={(event) => updatePreviewFile(index, event.target.value)}
                      className="min-h-[180px] w-full resize-y bg-transparent px-3 py-2 text-xs text-gray-200 outline-none"
                    />
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        ) : null}

        <DialogFooter className="flex flex-row justify-between">
          <div className="flex gap-2">
            {step > 1 ? (
              <Button variant="secondary" onClick={() => setStep(step - 1)}>
                Back
              </Button>
            ) : null}
          </div>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            {step === 1 ? (
              <Button onClick={() => setStep(2)}>Next</Button>
            ) : null}
            {step === 2 ? (
              <Button onClick={buildPreview} disabled={loadingPreview}>
                {loadingPreview ? 'Building...' : 'Preview'}
              </Button>
            ) : null}
            {step === 3 ? (
              <Button onClick={applyDocs} disabled={applying}>
                {applying ? 'Writing...' : 'Apply'}
              </Button>
            ) : null}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
