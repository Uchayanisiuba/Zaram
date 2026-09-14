import { describe, it, expect } from 'vitest';
import { workingLine } from './workingLine';
import type { ChatSource } from '@/services/chatClient';
import type { ChatToolCall } from '@/stores/chatStore';

const source = (kind: ChatSource['kind']): ChatSource => ({
  kind,
  url: null,
  title: null,
  excerpt: null,
  relevance: null,
  cited: true,
  number: null,
  egressId: null,
  bytesSent: null,
  origin: null,
  recordId: null,
});

const call = (over: Partial<ChatToolCall> = {}): ChatToolCall => ({
  server: 'code',
  tool: 'read_lines',
  verdict: 'allow',
  reason: '',
  target: 'readiness.py:156-181',
  ...over,
});

const idle = {
  isStreaming: true,
  streamingSources: [] as ChatSource[],
  streamingToolCalls: [] as ChatToolCall[],
  streamingImageProgress: null,
};

describe('the line under the orb while a reply is in flight', () => {
  it('says nothing until there is something measured to say', () => {
    // Nothing recalled and no tool used yet: the generic sentence stands.
    // A line here would be a claim about work that has not been reported.
    expect(workingLine(idle)).toBeNull();
    expect(workingLine({ ...idle, isStreaming: false, streamingToolCalls: [call()] })).toBeNull();
  });

  it('names what was recalled, by kind', () => {
    expect(
      workingLine({ ...idle, streamingSources: [source('memory'), source('memory'), source('document')] }),
    ).toBe('recalled 2 facts, 1 document');
  });

  it('carries the target of the latest call, in the past tense', () => {
    expect(workingLine({ ...idle, streamingToolCalls: [call({ tool: 'search_code', target: 'q' }), call()] })).toBe(
      'read readiness.py:156-181',
    );
  });

  it('says when a call is waiting on the person, or did not run', () => {
    expect(workingLine({ ...idle, streamingToolCalls: [call({ verdict: 'confirm' })] })).toBe(
      'waiting on you · read_lines',
    );
    expect(workingLine({ ...idle, streamingToolCalls: [call({ verdict: 'refuse' })] })).toBe(
      'did not run · read_lines',
    );
  });

  it('leaves an unknown tool under its own name', () => {
    expect(workingLine({ ...idle, streamingToolCalls: [call({ tool: 'some_new_tool', target: 'x' })] })).toBe(
      'some_new_tool x',
    );
  });

  it('joins recall, the latest call and a drawing in progress', () => {
    expect(
      workingLine({
        isStreaming: true,
        streamingSources: [source('memory')],
        streamingToolCalls: [call()],
        streamingImageProgress: { step: 4, total_steps: 10, index: 0, count: 1, percent: 40 },
      }),
    ).toBe('recalled 1 fact · read readiness.py:156-181 · drawing · 40%');
  });
});
