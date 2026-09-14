/**
 * What the orb is on, right now, in one line.
 *
 * While a reply is in flight the status label under the orb said "Thinking ·
 * Working on this machine." — true, and the same sentence for every reply.
 * The conversation column meanwhile lists every tool call as it lands. The
 * orb's half of the window was the less legible of the two during the only
 * seconds when it should be the more legible one.
 *
 * So the detail line becomes specific: what was recalled for this reply and
 * the latest thing a tool was aimed at. Both come from state the chat store
 * already holds — `streamingSources` arrive before the first token, and
 * `streamingToolCalls` carry a target — so nothing here is a new claim, and
 * nothing is guessed: with nothing recalled and no tool used yet the line is
 * `null` and the generic sentence stands.
 *
 * It is working state, and it clears with the reply (rule 7d). Past tense
 * throughout, because a call that has arrived has happened; "reading" would
 * assert something about the present that the stream does not report.
 */
import type { ChatSource, ImageProgress } from '@/services/chatClient';
import type { ChatToolCall } from '@/stores/chatStore';

/** One verb per tool that exists. Unknown tools fall back to their own name,
 *  which is honest and ages correctly when a tool is added. */
const DID: Record<string, string> = {
  search_code: 'searched',
  read_lines: 'read',
  list_files: 'listed',
  write_file: 'wrote',
  edit_file: 'edited',
  run_command: 'ran',
  find_symbol: 'looked up',
  read_library_docs: 'read docs for',
  plan: 'planned',
  start_app: 'started the app',
  stop_app: 'stopped the app',
  look_at_app: 'looked at the app',
};

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

function recalled(sources: ChatSource[]): string | null {
  if (!sources.length) return null;
  const facts = sources.filter((s) => s.kind === 'memory').length;
  const documents = sources.filter((s) => s.kind === 'document').length;
  const pages = sources.filter((s) => s.kind === 'web').length;
  const parts = [
    facts ? plural(facts, 'fact', 'facts') : '',
    documents ? plural(documents, 'document', 'documents') : '',
    pages ? plural(pages, 'page', 'pages') : '',
  ].filter(Boolean);
  return parts.length ? `recalled ${parts.join(', ')}` : null;
}

function latest(calls: ChatToolCall[]): string | null {
  const call = calls[calls.length - 1];
  if (!call) return null;
  if (call.verdict === 'confirm') return `waiting on you · ${call.tool}`;
  if (call.verdict === 'refuse') return `did not run · ${call.tool}`;
  const verb = DID[call.tool] ?? call.tool;
  return call.target ? `${verb} ${call.target}` : verb;
}

export function workingLine(s: {
  isStreaming: boolean;
  streamingSources: ChatSource[];
  streamingToolCalls: ChatToolCall[];
  streamingImageProgress: ImageProgress | null;
}): string | null {
  if (!s.isStreaming) return null;
  const parts = [recalled(s.streamingSources), latest(s.streamingToolCalls)];
  const progress = s.streamingImageProgress;
  if (progress && typeof progress.percent === 'number') {
    parts.push(`drawing · ${Math.round(progress.percent)}%`);
  }
  const said = parts.filter((p): p is string => Boolean(p));
  return said.length ? said.join(' · ') : null;
}
