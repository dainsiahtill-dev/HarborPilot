import { RefreshCw, X, FileText, Activity, AlertTriangle, TerminalSquare, Wrench } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch, connectWebSocket } from '@/api';

interface LogsModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialSourceId?: string | null;
  banner?: string | null;
  onDismissBanner?: () => void;
}

const LOG_SOURCES = [
  { id: 'pm-subprocess', label: 'PM Subprocess', path: 'state/ollama/PM_SUBPROCESS.log', channel: 'pm_subprocess' },
  { id: 'pm-report', label: 'PM Report', path: 'state/ollama/PM_REPORT.md', channel: 'pm_report' },
  { id: 'pm-log', label: 'PM Log (jsonl)', path: 'state/ollama/PM_LOG.jsonl', channel: 'pm_log' },
  { id: 'director', label: 'Director Subprocess', path: 'state/ollama/DIRECTOR_SUBPROCESS.log', channel: 'director_console' },
  { id: 'planner', label: 'Planner', path: 'state/ollama/PLANNER_RESPONSE.md', channel: 'planner' },
  { id: 'ollama', label: 'Ollama', path: 'state/ollama/OLLAMA_RESPONSE.md', channel: 'ollama' },
  { id: 'qa', label: 'QA', path: 'state/ollama/QA_RESPONSE.md', channel: 'qa' },
  { id: 'runlog', label: 'RunLog', path: 'state/ollama/RUNLOG.md', channel: 'runlog' },
];

type LogEvent =
  | { id: string; kind: 'section'; title: string; body: string; lifecycle?: 'open' | 'closed' }
  | { id: string; kind: 'json'; title?: string; value: unknown; raw: string; lifecycle?: 'open' | 'closed' }
  | { id: string; kind: 'tool'; tool: string; phase: 'starting' | 'ready' | 'info'; message?: string; lifecycle?: 'open' | 'closed' }
  | { id: string; kind: 'exec'; cwd?: string; cmd: string; ms?: number; exitCode?: number; lifecycle?: 'open' | 'closed' }
  | { id: string; kind: 'runStart'; version: string; meta: Record<string, string>; lifecycle?: 'open' | 'closed' }
  | { id: string; kind: 'role'; role: 'user' | 'thinking' | 'exec'; lifecycle?: 'open' | 'closed' }
  | { id: string; kind: 'command'; shell: string; cmd: string; cwd?: string; lifecycle?: 'open' | 'closed' }
  | { id: string; kind: 'commandResult'; status: 'ok' | 'fail'; exitCode?: number; ms?: number; cwd?: string; lifecycle?: 'open' | 'closed' }
  | { id: string; kind: 'table'; title?: string; columns: string[]; rows: string[][]; lifecycle?: 'open' | 'closed' }
  | {
      id: string;
      kind: 'fileContent';
      pathHint?: string;
      content: string;
      language?: string;
      encodingWarning?: boolean;
      lifecycle?: 'open' | 'closed';
    }
  | {
      id: string;
      kind: 'error';
      errorType: string;
      message: string;
      frames?: { file: string; line: number; codeLine?: string }[];
      raw: string;
      lifecycle?: 'open' | 'closed';
    }
  | { id: string; kind: 'metric'; label: string; value: string; lifecycle?: 'open' | 'closed' }
  | { id: string; kind: 'thinking'; title: string; body: string; lifecycle?: 'open' | 'closed' }
  | { id: string; kind: 'text'; level?: 'info' | 'warn'; text: string; lifecycle?: 'open' | 'closed' };

const SECTION_TITLES = ['GLOBAL REQUIREMENTS', 'CURRENT PLAN', 'GAP REPORT'];

function stripAnsi(text: string) {
  return text.replace(/\u001b\[[0-9;]*m/g, '');
}

function isSectionHeader(line: string) {
  const trimmed = line.trim();
  if (!trimmed) return false;
  if (/^##\s+/.test(trimmed)) return true;
  if (/^([A-Z0-9][A-Z0-9 _/()-]{2,}):\s*$/.test(trimmed)) return true;
  return SECTION_TITLES.some((title) => trimmed.toUpperCase().startsWith(title));
}

function parseJsonBlock(lines: string[], startIndex: number) {
  let buffer = stripAnsi(lines[startIndex]).trim();
  if (!buffer.startsWith('{') && !buffer.startsWith('[')) return null;
  for (let i = startIndex; i < Math.min(lines.length, startIndex + 200); i += 1) {
    if (i !== startIndex) {
      buffer += `\n${stripAnsi(lines[i])}`;
    }
    try {
      const value = JSON.parse(buffer);
      return { value, raw: buffer, endIndex: i };
    } catch {
      // keep accumulating
    }
  }
  return null;
}

function parseEvents(lines: string[]): LogEvent[] {
  const events: LogEvent[] = [];
  let index = 0;
  let currentRole: 'user' | 'thinking' | 'exec' | null = null;
  let lastCmd: { shell?: string; payload?: string } | null = null;
  let expectOutput: { kind: 'getChildItem' | 'getContent'; pathHint?: string } | null = null;
  while (index < lines.length) {
    const raw = lines[index] ?? '';
    const line = stripAnsi(raw);
    const trimmed = line.trim();
    if (!trimmed) {
      index += 1;
      continue;
    }

    const runHeaderMatch = trimmed.match(/^OpenAI Codex v([\d.]+)\b/);
    if (runHeaderMatch) {
      const version = runHeaderMatch[1];
      const meta: Record<string, string> = {};
      let j = index + 1;
      let dashesSeen = 0;
      while (j < lines.length) {
        const next = stripAnsi(lines[j] ?? '').trim();
        if (/^-{8,}$/.test(next)) {
          dashesSeen += 1;
          j += 1;
          if (dashesSeen >= 2) break;
          continue;
        }
        const kv = next.match(/^([a-zA-Z _-]+):\s*(.*)$/);
        if (kv) {
          meta[kv[1].trim()] = kv[2].trim();
        }
        j += 1;
      }
      events.push({ id: `run-${index}`, kind: 'runStart', version, meta });
      index = j;
      continue;
    }

    const roleMatch = trimmed.match(/^(user|thinking|exec)\s*$/i);
    if (roleMatch) {
      const role = roleMatch[1].toLowerCase() as 'user' | 'thinking' | 'exec';
      events.push({ id: `role-${index}`, kind: 'role', role });
      currentRole = role;
      index += 1;
      expectOutput = null;
      lastCmd = null;
      continue;
    }

    if (isSectionHeader(trimmed)) {
      const title = trimmed.replace(/^##\s+/, '').trim().replace(/:$/, '');
      const bodyLines: string[] = [];
      index += 1;
      while (index < lines.length) {
        const nextLine = stripAnsi(lines[index] ?? '');
        if (isSectionHeader(nextLine)) break;
        bodyLines.push(nextLine);
        index += 1;
      }
      events.push({
        id: `section-${index}-${title}`,
        kind: 'section',
        title,
        body: bodyLines.join('\n').trim(),
        lifecycle: 'closed',
      });
      continue;
    }

    const jsonBlock = parseJsonBlock(lines, index);
    if (jsonBlock) {
      events.push({
        id: `json-${index}`,
        kind: 'json',
        value: jsonBlock.value,
        raw: jsonBlock.raw,
        lifecycle: 'closed',
      });
      index = jsonBlock.endIndex + 1;
      continue;
    }

    const psCmdMatch = trimmed.match(/^"([^"]*powershell\.exe)"\s+-Command\s+(.*)$/i);
    if (psCmdMatch) {
      const shell = psCmdMatch[1];
      const payloadRaw = psCmdMatch[2].trim();
      let payload = payloadRaw;
      const q = payloadRaw.match(/^'(.*)'$/) || payloadRaw.match(/^"(.*)"$/);
      if (q) payload = q[1];
      events.push({ id: `cmd-${index}`, kind: 'command', shell, cmd: payload, lifecycle: 'closed' });
      lastCmd = { shell, payload };
      expectOutput = null;
      index += 1;
      continue;
    }

    const execMatch = trimmed.match(/^\[(empty:cmd|CMD)\]\s+Running:\s+(.+)$/);
    if (execMatch) {
      events.push({ id: `exec-${index}`, kind: 'exec', cmd: execMatch[1], lifecycle: 'closed' });
      index += 1;
      continue;
    }

    const okMatch = trimmed.match(/\bin\s+(.+?)\s+succeeded\s+in\s+(\d+)ms:?\s*$/);
    if (okMatch) {
      const cwd = okMatch[1].trim();
      const ms = Number(okMatch[2]);
      events.push({ id: `res-${index}`, kind: 'commandResult', status: 'ok', ms, cwd, exitCode: 0, lifecycle: 'closed' });
      const payload = lastCmd?.payload || '';
      if (/Get-ChildItem\b/i.test(payload)) {
        expectOutput = { kind: 'getChildItem' };
      } else if (/Get-Content\b/i.test(payload)) {
        const pathMatch =
          payload.match(/-Path\s+([^\s'"]+)/i) ||
          payload.match(/-Path\s+'([^']+)'/i) ||
          payload.match(/-Path\s+"([^"]+)"/i);
        expectOutput = { kind: 'getContent', pathHint: pathMatch ? pathMatch[1] : undefined };
      } else {
        expectOutput = null;
      }
      index += 1;
      continue;
    }

    const execResultMatch = trimmed.match(/^(.*) in (.+) (succeeded|failed) in (\d+)ms:?\s*$/i);
    if (execResultMatch) {
      const cmd = execResultMatch[1].trim();
      const cwd = execResultMatch[2].trim();
      const ok = execResultMatch[3].toLowerCase() === 'succeeded';
      const ms = Number(execResultMatch[4]);
      events.push({ id: `exec-${index}`, kind: 'exec', cmd, cwd, ms, exitCode: ok ? 0 : 1, lifecycle: 'closed' });
      index += 1;
      continue;
    }

    if (trimmed.toLowerCase().startsWith('mcp:')) {
      const message = trimmed.slice(4).trim();
      let phase: 'starting' | 'ready' | 'info' = 'info';
      if (message.toLowerCase().includes('starting')) phase = 'starting';
      if (message.toLowerCase().includes('ready')) phase = 'ready';
      events.push({ id: `tool-${index}`, kind: 'tool', tool: 'mcp', phase, message, lifecycle: 'closed' });
      index += 1;
      continue;
    }

    const mcpStartupMatch = trimmed.match(/^mcp startup:\s*ready:\s*(.+)\s*$/i);
    if (mcpStartupMatch) {
      const list = mcpStartupMatch[1].split(',').map((s) => s.trim()).filter(Boolean);
      list.forEach((tool, k) => {
        events.push({ id: `tool-${index}-${k}`, kind: 'tool', tool, phase: 'ready', lifecycle: 'closed' });
      });
      index += 1;
      continue;
    }

    if (trimmed.toLowerCase().startsWith('thinking')) {
      const nextLine = stripAnsi(lines[index + 1] ?? '').trim();
      const isThinkingHeader = /^\*\*.+\*\*$/.test(nextLine);
      if (isThinkingHeader) {
        const header = nextLine.replace(/^\*\*|\*\*$/g, '').trim() || nextLine;
        const bodyLines: string[] = [];
        let j = index + 2;
        while (j < lines.length) {
          const candidate = stripAnsi(lines[j] ?? '');
          const candidateTrimmed = candidate.trim();
          const isBoundary =
            isSectionHeader(candidateTrimmed) ||
            candidateTrimmed.toLowerCase().startsWith('thinking') ||
            /^\[(empty:cmd|CMD)\]\s+Running:/.test(candidateTrimmed) ||
            /^(.*) in (.+) (succeeded|failed) in (\d+)ms:?\s*$/i.test(candidateTrimmed) ||
            candidateTrimmed.toLowerCase().startsWith('mcp:') ||
            candidateTrimmed.startsWith('Traceback') ||
            candidateTrimmed.includes('SyntaxError') ||
            candidateTrimmed.includes('Exception') ||
            candidateTrimmed.includes('Error:') ||
            candidateTrimmed.startsWith('{') ||
            candidateTrimmed.startsWith('[');
          if (isBoundary) break;
          bodyLines.push(candidate);
          if (bodyLines.length > 200) break;
          j += 1;
        }
        while (bodyLines.length && !bodyLines[bodyLines.length - 1].trim()) {
          bodyLines.pop();
        }
        events.push({
          id: `thinking-${index}`,
          kind: 'thinking',
          title: header,
          body: bodyLines.join('\n').trim(),
          lifecycle: 'closed',
        });
        index = j;
        continue;
      }
    }

    if (expectOutput?.kind === 'getChildItem') {
      const dirMatch = trimmed.match(/^Directory:\s+(.+)$/);
      if (dirMatch) {
        let j = index + 1;
        let header = stripAnsi(lines[j] ?? '').trim();
        let sep = stripAnsi(lines[j + 1] ?? '').trim();
        let columns: string[] = [];
        if (header && sep && /-{2,}/.test(sep)) {
          columns = header.split(/\s{2,}/);
          const rows: string[][] = [];
          j += 2;
          while (j < lines.length) {
            const rowLine = stripAnsi(lines[j] ?? '');
            const t = rowLine.trim();
            if (!t) break;
            if (isSectionHeader(t)) break;
            if (/^(user|thinking|exec)\s*$/.test(t)) break;
            if (/^"([^"]*powershell\.exe)"/i.test(t)) break;
            if (/^mcp:/i.test(t)) break;
            const cols = rowLine.trim().split(/\s{2,}/);
            if (cols.length >= Math.min(4, columns.length)) {
              rows.push(cols);
              j += 1;
            } else {
              break;
            }
          }
          events.push({ id: `table-${index}`, kind: 'table', title: dirMatch[1], columns, rows, lifecycle: 'closed' });
          index = j;
          expectOutput = null;
          continue;
        }
      }
    }

    if (expectOutput?.kind === 'getContent') {
      const bodyLines: string[] = [];
      let j = index;
      while (j < lines.length) {
        const t = stripAnsi(lines[j] ?? '').trim();
        if (!t) {
          j += 1;
          if (bodyLines.length) break;
          continue;
        }
        if (isSectionHeader(t)) break;
        if (/^(user|thinking|exec)\s*$/.test(t)) break;
        if (/^"([^"]*powershell\.exe)"/i.test(t)) break;
        if (/^mcp:/i.test(t)) break;
        if (/^-{8,}$/.test(t)) break;
        bodyLines.push(stripAnsi(lines[j] ?? ''));
        j += 1;
        if (bodyLines.length > 500) break;
      }
      const content = bodyLines.join('\n');
      const hasReplacement = /\uFFFD/.test(content);
      const hasGarbled = /[鍓洰鍒欏彲閲岄亾銆?]/.test(content);
      const encodingWarning = hasReplacement || hasGarbled;
      let language: string | undefined;
      const hint = expectOutput.pathHint || '';
      if (/\.(ts|tsx)$/.test(hint)) language = 'typescript';
      else if (/\.js$/.test(hint)) language = 'javascript';
      else if (/\.md$/.test(hint)) language = 'markdown';
      else if (/\.py$/.test(hint)) language = 'python';
      events.push({
        id: `file-${index}`,
        kind: 'fileContent',
        pathHint: expectOutput.pathHint,
        content,
        language,
        encodingWarning,
        lifecycle: 'closed',
      });
      index = j;
      expectOutput = null;
      continue;
    }

    const tokensMatchInline = trimmed.match(/^tokens used[:\s]*([\d,]+(empty:\.\d+)?)$/i);
    if (tokensMatchInline) {
      events.push({
        id: `metric-${index}`,
        kind: 'metric',
        label: 'tokens used',
        value: tokensMatchInline[1],
        lifecycle: 'closed',
      });
      index += 1;
      continue;
    }
    if (trimmed.toLowerCase() === 'tokens used') {
      let lookahead = index + 1;
      let matched = false;
      while (lookahead < lines.length) {
        const nextLine = stripAnsi(lines[lookahead] ?? '').trim();
        if (!nextLine) {
          lookahead += 1;
          continue;
        }
        if (/^\d{1,3}(,\d{3})*(\.\d+)?$/.test(nextLine) || /^\d+(\.\d+)?$/.test(nextLine)) {
          events.push({
            id: `metric-${index}`,
            kind: 'metric',
            label: 'tokens used',
            value: nextLine,
            lifecycle: 'closed',
          });
          index = lookahead + 1;
          matched = true;
        }
        break;
      }
      if (matched) {
        continue;
      }
    }

    if (
      trimmed.startsWith('Traceback') ||
      trimmed.includes('SyntaxError') ||
      trimmed.includes('Exception') ||
      trimmed.includes('Error:')
    ) {
      const blockLines: string[] = [trimmed];
      let j = index + 1;
      while (j < lines.length) {
        const next = stripAnsi(lines[j] ?? '');
        if (!next.trim()) break;
        if (isSectionHeader(next)) break;
        blockLines.push(next);
        if (blockLines.length > 20) break;
        j += 1;
      }
      const message = blockLines[blockLines.length - 1] || 'Error';
      events.push({
        id: `error-${index}`,
        kind: 'error',
        errorType: message.split(':')[0] || 'Error',
        message,
        raw: blockLines.join('\n'),
        lifecycle: 'closed',
      });
      index = j + 1;
      continue;
    }

    events.push({ id: `text-${index}`, kind: 'text', text: trimmed, lifecycle: 'closed' });
    index += 1;
  }
  return events;
}

class StreamingParser {
  events: LogEvent[] = [];
  mode: 'idle' | 'user' | 'thinking' | 'exec' = 'idle';
  lastCmd: { shell?: string; payload?: string } | null = null;
  expectOutput: { kind: 'getChildItem' | 'getContent'; pathHint?: string } | null = null;
  json: { id: string; depth: number; raw: string } | null = null;
  table: { id: string; title?: string; columns: string[]; rows: string[][]; headerSeen: boolean } | null = null;
  file: { id: string; pathHint?: string; content: string } | null = null;
  text: { id: string; buffer: string[] } | null = null;
  open(e: LogEvent) {
    e.lifecycle = 'open';
    this.events.push(e);
    return e.id;
  }
  close(id: string) {
    const idx = this.events.findIndex((x) => x.id === id);
    if (idx >= 0) this.events[idx].lifecycle = 'closed';
  }
  feedLine(line: string) {
    const trimmed = stripAnsi(line).trim();
    if (!trimmed) return;
    if (/^(user|thinking|exec)\s*$/i.test(trimmed)) {
      const role = trimmed.toLowerCase() as 'user' | 'thinking' | 'exec';
      this.open({ id: `role-${this.events.length}`, kind: 'role', role, lifecycle: 'open' });
      this.close(this.events[this.events.length - 1].id);
      this.mode = role;
      this.flushOpenBlocks();
      return;
    }
    if (/^"([^"]*powershell\.exe)"\s+-Command\s+/.test(trimmed)) {
      const m = trimmed.match(/^"([^"]*powershell\.exe)"\s+-Command\s+(.*)$/i);
      if (m) {
        const shell = m[1];
        let payload = m[2].trim();
        const q = payload.match(/^'(.*)'$/) || payload.match(/^"(.*)"$/);
        if (q) payload = q[1];
        this.lastCmd = { shell, payload };
        this.open({ id: `cmd-${this.events.length}`, kind: 'command', shell, cmd: payload, lifecycle: 'open' });
        return;
      }
    }
    const ok = trimmed.match(/\bin\s+(.+?)\s+succeeded\s+in\s+(\d+)ms:?\s*$/);
    const fail = trimmed.match(/\bexited\s+(-?\d+)\s+in\s+(\d+)ms:?\s*$/);
    if (ok) {
      const cwd = ok[1].trim();
      const ms = Number(ok[2]);
      this.open({ id: `res-${this.events.length}`, kind: 'commandResult', status: 'ok', ms, cwd, exitCode: 0, lifecycle: 'open' });
      this.close(this.events[this.events.length - 1].id);
      const payload = this.lastCmd?.payload || '';
      if (/Get-ChildItem\b/i.test(payload)) this.expectOutput = { kind: 'getChildItem' };
      else if (/Get-Content\b/i.test(payload)) {
        const pathMatch =
          payload.match(/-Path\s+([^\s'"]+)/i) ||
          payload.match(/-Path\s+'([^']+)'/i) ||
          payload.match(/-Path\s+"([^"]+)"/i);
        this.expectOutput = { kind: 'getContent', pathHint: pathMatch ? pathMatch[1] : undefined };
      } else this.expectOutput = null;
      return;
    }
    if (fail) {
      const code = Number(fail[1]);
      const ms = Number(fail[2]);
      this.open({ id: `res-${this.events.length}`, kind: 'commandResult', status: 'fail', ms, exitCode: code, lifecycle: 'open' });
      this.close(this.events[this.events.length - 1].id);
      this.expectOutput = null;
      return;
    }
    if (this.expectOutput?.kind === 'getChildItem') {
      if (/^Directory:\s+/.test(trimmed)) {
        const title = trimmed.replace(/^Directory:\s+/, '');
        this.table = { id: `table-${this.events.length}`, title, columns: [], rows: [], headerSeen: false };
        this.open({ id: this.table.id, kind: 'table', title, columns: [], rows: [], lifecycle: 'open' });
        return;
      }
      if (this.table && !this.table.headerSeen) {
        const sepCandidate = trimmed;
        const nextIsSep = /-{2,}/.test(sepCandidate);
        if (!nextIsSep) {
          this.table.columns = trimmed.split(/\s{2,}/);
          return;
        } else {
          this.table.headerSeen = true;
          return;
        }
      }
      if (this.table && this.table.headerSeen) {
        const cols = trimmed.split(/\s{2,}/);
        if (cols.length >= Math.min(4, this.table.columns.length)) {
          this.table.rows.push(cols);
          const idx = this.events.findIndex((x) => x.id === this.table!.id);
          if (idx >= 0 && this.events[idx].kind === 'table') {
            this.events[idx] = { ...this.events[idx], rows: [...this.table.rows], columns: [...this.table.columns] };
          }
          return;
        } else {
          this.close(this.table.id);
          this.table = null;
          this.expectOutput = null;
        }
      }
    }
    if (this.expectOutput?.kind === 'getContent') {
      if (!this.file) {
        const id = `file-${this.events.length}`;
        this.file = { id, pathHint: this.expectOutput.pathHint, content: '' };
        this.open({ id, kind: 'fileContent', pathHint: this.expectOutput.pathHint, content: '', lifecycle: 'open' });
      }
      this.file.content += (this.file.content ? '\n' : '') + stripAnsi(line);
      const idx = this.events.findIndex((x) => x.id === this.file!.id);
      if (idx >= 0 && this.events[idx].kind === 'fileContent') {
        const content = this.file.content;
        const hasReplacement = /\uFFFD/.test(content);
        const hasGarbled = /[鍓洰鍒欏彲閲岄亾銆?]/.test(content);
        const encodingWarning = hasReplacement || hasGarbled;
        this.events[idx] = {
          ...this.events[idx],
          content,
          encodingWarning,
        } as LogEvent;
      }
      return;
    }
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
      if (!this.json) {
        const id = `json-${this.events.length}`;
        this.json = { id, depth: 0, raw: '' };
        this.open({ id, kind: 'json', value: undefined, raw: '', lifecycle: 'open' });
      }
      this.json.raw += (this.json.raw ? '\n' : '') + stripAnsi(line);
      const delta = (line.match(/{/g) || []).length - (line.match(/}/g) || []).length + (line.match(/\[/g) || []).length - (line.match(/]/g) || []).length;
      this.json.depth += delta;
      const idx = this.events.findIndex((x) => x.id === this.json!.id);
      if (idx >= 0 && this.events[idx].kind === 'json') {
        this.events[idx] = { ...this.events[idx], raw: this.json.raw } as LogEvent;
      }
      if (this.json.depth <= 0) {
        const id = this.json.id;
        try {
          const val = JSON.parse(this.json.raw);
          const jdx = this.events.findIndex((x) => x.id === id);
          if (jdx >= 0 && this.events[jdx].kind === 'json') {
            this.events[jdx] = { ...this.events[jdx], value: val } as LogEvent;
          }
        } catch {}
        this.close(id);
        this.json = null;
      }
      return;
    }
    if (!this.text) {
      const id = `text-${this.events.length}`;
      this.text = { id, buffer: [] };
      this.open({ id, kind: 'text', text: '', lifecycle: 'open' });
    }
    this.text.buffer.push(trimmed);
    const idx = this.events.findIndex((x) => x.id === this.text!.id);
    if (idx >= 0 && this.events[idx].kind === 'text') {
      const text = this.text.buffer.join('\n');
      this.events[idx] = { ...this.events[idx], text } as LogEvent;
    }
  }
  flushOpenBlocks() {
    if (this.table) {
      this.close(this.table.id);
      this.table = null;
    }
    if (this.file) {
      this.close(this.file.id);
      this.file = null;
    }
    if (this.json) {
      this.close(this.json.id);
      this.json = null;
    }
    if (this.text) {
      this.close(this.text.id);
      this.text = null;
    }
    this.expectOutput = null;
  }
}

function SmartText({ text }: { text: string }) {
  const max = 400;
  if (text.length <= max) {
    return <div className="text-xs text-gray-200 whitespace-pre-wrap">{text}</div>;
  }
  return (
    <details className="text-xs text-gray-200 whitespace-pre-wrap">
      <summary className="cursor-pointer text-gray-400">展开内容</summary>
      {text}
    </details>
  );
}

export function LogsModal({
  isOpen,
  onClose,
  initialSourceId,
  banner,
  onDismissBanner,
}: LogsModalProps) {
  const [active, setActive] = useState(LOG_SOURCES[0].id);
  const [lines, setLines] = useState<string[]>([]);
  const [mtime, setMtime] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(false);
  const [viewMode, setViewMode] = useState<'raw' | 'smart' | 'json'>('smart');
  const [filter, setFilter] = useState<'all' | 'error' | 'exec' | 'tool'>('all');
  const [query, setQuery] = useState('');
  const socketRef = useRef<WebSocket | null>(null);
  const [streamEvents, setStreamEvents] = useState<LogEvent[]>([]);
  const parserRef = useRef<StreamingParser | null>(null);

  const activeSource = useMemo(
    () => LOG_SOURCES.find((item) => item.id === active) || LOG_SOURCES[0],
    [active]
  );

  const allowSmart = active === 'pm-subprocess';
  const allowJson = active === 'pm-log';
  const allowRaw = active !== 'pm-log';

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/files/read?path=${encodeURIComponent(activeSource.path)}&tail_lines=400`);
      if (!res.ok) {
        throw new Error('Failed to load log');
      }
      const payload = (await res.json()) as { content?: string; mtime?: string };
      setLines(payload.content ? payload.content.split('\n') : []);
      setMtime(payload.mtime || '');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load log');
      setLines([]);
      setMtime('');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isOpen) return;
    refresh();
  }, [isOpen, active]);

  useEffect(() => {
    if (!isOpen) return;
    if (initialSourceId) {
      const exists = LOG_SOURCES.some((item) => item.id === initialSourceId);
      setActive(exists ? initialSourceId : LOG_SOURCES[0].id);
    }
  }, [isOpen, initialSourceId]);

  useEffect(() => {
    if (!isOpen) return;
    if (active === 'pm-subprocess') {
      setViewMode('smart');
    } else if (active === 'pm-log') {
      setViewMode('json');
    } else {
      setViewMode('raw');
    }
  }, [isOpen, active]);

  useEffect(() => {
    if (!isOpen) return;
    let activeSocket: WebSocket | null = null;
    let alive = true;

    const connect = async () => {
      try {
        activeSocket = await connectWebSocket();
      } catch {
        if (alive) setLive(false);
        return;
      }

      socketRef.current = activeSocket;
      if (!alive) return;

      activeSocket.onopen = () => {
        setLive(true);
        activeSocket?.send(
          JSON.stringify({
            type: 'subscribe',
            channels: [activeSource.channel],
            tail_lines: 200,
          })
        );
      };

      activeSocket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.channel !== activeSource.channel) return;
          if (payload.type === 'snapshot' && Array.isArray(payload.lines)) {
            setLines(payload.lines);
            setStreamEvents(parseEvents(payload.lines));
            parserRef.current = new StreamingParser();
            return;
          }
          if (payload.type === 'line' && payload.text) {
            setLines((prev) => [...prev, payload.text].slice(-1000));
            if (!parserRef.current) parserRef.current = new StreamingParser();
            parserRef.current.feedLine(payload.text);
            setStreamEvents([...parserRef.current.events]);
          }
        } catch {
          // ignore malformed payloads
        }
      };

      activeSocket.onclose = () => {
        if (alive) setLive(false);
      };

      activeSocket.onerror = () => {
        if (alive) setLive(false);
      };
    };

    connect();

    return () => {
      alive = false;
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [isOpen, activeSource.channel]);

  const smartEvents = useMemo(() => {
    if (streamEvents.length > 0) return streamEvents;
    return parseEvents(lines);
  }, [lines, streamEvents]);
  const jsonEvents = useMemo(() => {
    if (active !== 'pm-log') return [];
    return lines
      .map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) return null;
        try {
          return { id: `jsonl-${idx}`, raw: trimmed, value: JSON.parse(trimmed) };
        } catch {
          return { id: `jsonl-${idx}`, raw: trimmed, value: null };
        }
      })
      .filter(Boolean) as { id: string; raw: string; value: unknown | null }[];
  }, [active, lines]);

  const filteredEvents = useMemo(() => {
    return smartEvents.filter((event) => {
      if (filter !== 'all' && event.kind !== filter) {
        return false;
      }
      if (!query.trim()) return true;
      const haystack =
        event.kind === 'json'
          ? event.raw
          : event.kind === 'error'
            ? event.raw
            : event.kind === 'section'
              ? `${event.title}\n${event.body}`
              : event.kind === 'exec'
                ? `${event.cmd} ${event.cwd ?? ''}`
                : event.kind === 'tool'
                  ? `${event.tool} ${event.message ?? ''}`
                  : event.kind === 'thinking'
                    ? event.text
                    : event.kind === 'runStart'
                      ? `${event.version} ${Object.values(event.meta).join(' ')}`
                      : event.kind === 'role'
                        ? event.role
                        : event.kind === 'command'
                          ? `${event.shell} ${event.cmd}`
                          : event.kind === 'commandResult'
                            ? `${event.status} ${event.cwd ?? ''} ${event.ms ?? ''}`
                            : event.kind === 'table'
                              ? `${event.title ?? ''} ${event.columns.join(' ')}`
                              : event.kind === 'fileContent'
                                ? `${event.pathHint ?? ''} ${event.content.slice(0, 100)}`
                                : event.text;
      return haystack.toLowerCase().includes(query.toLowerCase());
    });
  }, [smartEvents, filter, query]);

  const summary = useMemo(() => {
    let errors = 0;
    let execs = 0;
    let tools = 0;
    smartEvents.forEach((event) => {
      if (event.kind === 'error') errors += 1;
      if (event.kind === 'exec') execs += 1;
      if (event.kind === 'tool') tools += 1;
    });
    return { errors, execs, tools };
  }, [smartEvents]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[#252526] border border-gray-700 rounded-lg w-full max-w-3xl max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <div className="flex items-center gap-2">
            <FileText className="size-4 text-blue-400" />
            <h2 className="text-lg font-semibold text-gray-200">运行日志</h2>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={refresh}
              className="p-2 text-gray-400 hover:text-gray-200 hover:bg-white/5 rounded transition-colors"
              disabled={loading}
            >
              <RefreshCw className="size-4" />
            </button>
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-gray-200 hover:bg-white/5 rounded transition-colors"
            >
              <X className="size-4" />
            </button>
          </div>
        </div>

        {banner ? (
          <div className="mx-4 mt-3 max-h-40 overflow-auto rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200 whitespace-pre-wrap">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1">{banner}</div>
              {onDismissBanner ? (
                <button
                  onClick={onDismissBanner}
                  className="ml-2 text-red-200/70 hover:text-red-100 transition-colors"
                  aria-label="Dismiss"
                >
                  <X className="size-4" />
                </button>
              ) : null}
            </div>
          </div>
        ) : null}

        <div className="px-4 pt-3">
          <div className="flex items-center gap-2">
            {LOG_SOURCES.map((item) => (
              <button
                key={item.id}
                onClick={() => setActive(item.id)}
                className={`px-3 py-1.5 text-sm rounded transition-colors ${
                  active === item.id
                    ? 'bg-blue-500/20 text-blue-300'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {item.label}
              </button>
            ))}
            <span className="ml-auto text-xs text-gray-500">更新时间: {mtime || '-'}</span>
            <span className="text-xs text-gray-500 flex items-center gap-1">
              <Activity className="size-3" />
              {live ? '实时' : '离线'}
            </span>
          </div>
        </div>

        <div className="px-4 pt-3 flex items-center gap-2">
          <div className="flex items-center gap-1 rounded-md border border-gray-700 bg-gray-800/80 p-1">
            <button
              onClick={() => allowRaw && setViewMode('raw')}
              disabled={!allowRaw}
              className={`px-2 py-1 text-xs rounded ${
                viewMode === 'raw' ? 'bg-blue-500/30 text-blue-200' : 'text-gray-400 hover:text-gray-200'
              } ${!allowRaw ? 'opacity-40 cursor-not-allowed' : ''}`}
            >
              Raw
            </button>
            <button
              onClick={() => allowSmart && setViewMode('smart')}
              disabled={!allowSmart}
              className={`px-2 py-1 text-xs rounded ${
                viewMode === 'smart' ? 'bg-blue-500/30 text-blue-200' : 'text-gray-400 hover:text-gray-200'
              } ${!allowSmart ? 'opacity-40 cursor-not-allowed' : ''}`}
            >
              Smart
            </button>
            <button
              onClick={() => allowJson && setViewMode('json')}
              disabled={!allowJson}
              className={`px-2 py-1 text-xs rounded ${
                viewMode === 'json' ? 'bg-blue-500/30 text-blue-200' : 'text-gray-400 hover:text-gray-200'
              } ${!allowJson ? 'opacity-40 cursor-not-allowed' : ''}`}
            >
              JSON
            </button>
          </div>
          {viewMode === 'smart' ? (
            <>
              <div className="ml-2 flex items-center gap-2 text-xs text-gray-400">
                <span className="flex items-center gap-1">
                  <AlertTriangle className="size-3 text-red-300" />
                  {summary.errors}
                </span>
                <span className="flex items-center gap-1">
                  <TerminalSquare className="size-3 text-blue-300" />
                  {summary.execs}
                </span>
                <span className="flex items-center gap-1">
                  <Wrench className="size-3 text-emerald-300" />
                  {summary.tools}
                </span>
              </div>
              <select
                className="ml-auto bg-gray-800 text-xs text-gray-300 border border-gray-700 rounded px-2 py-1"
                value={filter}
                onChange={(event) => setFilter(event.target.value as typeof filter)}
              >
                <option value="all">All</option>
                <option value="error">Errors</option>
                <option value="exec">Exec</option>
                <option value="tool">Tool</option>
              </select>
              <input
                className="bg-gray-800 text-xs text-gray-300 border border-gray-700 rounded px-2 py-1"
                placeholder="Search..."
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </>
          ) : null}
        </div>

        <div className="flex-1 overflow-auto p-4">
          {error ? (
            <div className="text-sm text-red-300">{error}</div>
          ) : viewMode === 'raw' ? (
            <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap">
              {loading ? '加载中...' : lines.join('\n') || '(空)'}
            </pre>
          ) : viewMode === 'json' ? (
            <div className="space-y-2">
              {loading ? (
                <div className="text-sm text-gray-300">Loading...</div>
              ) : jsonEvents.length === 0 ? (
                <div className="text-sm text-gray-400">(empty)</div>
              ) : (
                jsonEvents.map((event) => (
                  <pre key={event.id} className="text-xs text-gray-200 font-mono whitespace-pre-wrap">
                    {event.value ? JSON.stringify(event.value, null, 2) : event.raw}
                  </pre>
                ))
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {loading ? (
                <div className="text-sm text-gray-300">加载中...</div>
              ) : filteredEvents.length === 0 ? (
                <div className="text-sm text-gray-400">(空)</div>
              ) : (
                filteredEvents.map((event) => {
                  if (event.kind === 'section') {
                    return (
                      <details key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                        <summary className="cursor-pointer text-sm text-blue-200">{event.title}</summary>
                        <div className="mt-2 text-xs text-gray-200 whitespace-pre-wrap">
                          {event.body || '(empty)'}
                        </div>
                      </details>
                    );
                  }
                  if (event.kind === 'runStart') {
                    return (
                      <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                        <div className="text-xs text-gray-400">Run</div>
                        <div className="text-sm text-gray-200">OpenAI Codex v{event.version}</div>
                        <div className="mt-1 text-xs text-gray-400">
                          {Object.entries(event.meta)
                            .map(([k, v]) => `${k}: ${v}`)
                            .join(' • ')}
                        </div>
                      </div>
                    );
                  }
                  if (event.kind === 'role') {
                    return (
                      <div key={event.id} className="text-xs text-gray-400">
                        [{event.role}]
                      </div>
                    );
                  }
                  if (event.kind === 'json') {
                    return (
                      <details key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                        <summary className="cursor-pointer text-sm text-emerald-200">JSON</summary>
                        <pre className="mt-2 text-xs text-gray-200 whitespace-pre-wrap">
                          {JSON.stringify(event.value, null, 2)}
                        </pre>
                      </details>
                    );
                  }
                  if (event.kind === 'command') {
                    return (
                      <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                        <div className="text-xs text-gray-400">Exec</div>
                        <div className="text-sm text-gray-200 break-all">{event.cmd}</div>
                        <div className="mt-1 text-xs text-gray-400">{event.shell}</div>
                        {event.lifecycle === 'open' ? <div className="mt-1 text-xs text-blue-300">streaming…</div> : null}
                      </div>
                    );
                  }
                  if (event.kind === 'commandResult') {
                    return (
                      <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                        <div className={`text-xs ${event.status === 'ok' ? 'text-emerald-300' : 'text-red-300'}`}>
                          {event.status === 'ok' ? 'Succeeded' : 'Failed'}
                        </div>
                        <div className="mt-1 text-xs text-gray-400">
                          {event.cwd ? `cwd: ${event.cwd} ` : ''}
                          {typeof event.ms === 'number' ? `• ${event.ms}ms ` : ''}
                          {typeof event.exitCode === 'number' ? `• exit ${event.exitCode}` : ''}
                        </div>
                        {event.lifecycle === 'open' ? <div className="mt-1 text-xs text-blue-300">streaming…</div> : null}
                      </div>
                    );
                  }
                  if (event.kind === 'exec') {
                    return (
                      <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                        <div className="text-xs text-gray-400">Exec</div>
                        <div className="text-sm text-gray-200 break-all">{event.cmd}</div>
                        <div className="mt-1 text-xs text-gray-400">
                          {event.cwd ? `cwd: ${event.cwd} ` : ''}
                          {typeof event.ms === 'number' ? `• ${event.ms}ms ` : ''}
                          {typeof event.exitCode === 'number' ? `• exit ${event.exitCode}` : ''}
                        </div>
                      </div>
                    );
                  }
                  if (event.kind === 'tool') {
                    return (
                      <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                        <div className="text-xs text-gray-400">Tool</div>
                        <div className="text-sm text-gray-200">
                          {event.tool} • {event.phase}
                        </div>
                        {event.message ? <div className="mt-1 text-xs text-gray-300">{event.message}</div> : null}
                      </div>
                    );
                  }
                  if (event.kind === 'table') {
                    return (
                      <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                        <div className="text-xs text-gray-400">Directory</div>
                        <div className="text-xs text-gray-400">{event.title || ''}</div>
                        {event.lifecycle === 'open' ? <div className="text-xs text-blue-300">加载中…</div> : null}
                        <div className="mt-2 overflow-auto">
                          <table className="w-full text-xs text-gray-200">
                            <thead>
                              <tr>
                                {event.columns.map((c, i) => (
                                  <th key={i} className="text-left font-medium pr-4">
                                    {c}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {event.rows.map((r, ri) => (
                                <tr key={ri}>
                                  {r.map((cell, ci) => (
                                    <td key={ci} className="pr-4 py-0.5">
                                      {cell}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    );
                  }
                  if (event.kind === 'fileContent') {
                    return (
                      <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                        <div className="text-xs text-gray-400">
                          File {event.pathHint || ''} {event.encodingWarning ? ' • encoding warning' : ''}
                        </div>
                        {event.lifecycle === 'open' ? <div className="text-xs text-blue-300">streaming…</div> : null}
                        <pre className="mt-2 text-xs text-gray-200 whitespace-pre-wrap">{event.content || '(empty)'}</pre>
                      </div>
                    );
                  }
                  if (event.kind === 'metric') {
                    return (
                      <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                        <div className="text-xs text-gray-400">Metric</div>
                        <div className="text-sm text-gray-200">
                          {event.label}: <span className="font-semibold text-emerald-200">{event.value}</span>
                        </div>
                      </div>
                    );
                  }
                  if (event.kind === 'thinking') {
                    return (
                      <details key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                        <summary className="cursor-pointer text-sm text-purple-200">Thinking</summary>
                        <div className="mt-2 text-xs text-gray-200">
                          <div className="font-semibold text-purple-100">{event.title}</div>
                          {event.body ? (
                            <div className="mt-2 whitespace-pre-wrap text-gray-200">{event.body}</div>
                          ) : null}
                        </div>
                      </details>
                    );
                  }
                  if (event.kind === 'error') {
                    return (
                      <details
                        key={event.id}
                        className="rounded border border-red-500/40 bg-red-500/10 p-3 text-red-200"
                      >
                        <summary className="cursor-pointer text-sm">{event.message}</summary>
                        <pre className="mt-2 text-xs text-red-100 whitespace-pre-wrap">{event.raw}</pre>
                      </details>
                    );
                  }
                  return (
                    <div key={event.id} className="rounded border border-gray-700 bg-gray-900/40 p-3">
                      <SmartText text={event.text} />
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
