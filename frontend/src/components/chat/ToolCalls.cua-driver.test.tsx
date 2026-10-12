import { describe, it, expect } from 'vitest';
import { summarise } from './ToolCalls';
import type { ChatToolCall } from '@/stores/chatStore';

const call = (tool: string, verdict: string, server: string): ChatToolCall => ({
  tool,
  verdict,
  server,
  reason: '',
  target: '',
});

describe('ToolCalls summarise - cua-driver tools', () => {
  it('summarises screenshot tools', () => {
    const calls = [
      call('get_desktop_state', 'allow', 'cua-driver'),
    ];
    expect(summarise(calls)).toBe('Captured desktop');
  });

  it('summarises multiple screenshots', () => {
    const calls = [
      call('get_desktop_state', 'allow', 'cua-driver'),
      call('get_desktop_state', 'allow', 'cua-driver'),
    ];
    expect(summarise(calls)).toBe('Captured desktop 2×');
  });

  it('summarises window inspection', () => {
    const calls = [
      call('get_window_state', 'allow', 'cua-driver'),
    ];
    expect(summarise(calls)).toBe('Inspected window');
  });

  it('summarises accessibility tree', () => {
    const calls = [
      call('get_accessibility_tree', 'allow', 'cua-driver'),
    ];
    expect(summarise(calls)).toBe('Read accessibility tree');
  });

  it('summarises list windows', () => {
    const calls = [
      call('list_windows', 'allow', 'cua-driver'),
    ];
    expect(summarise(calls)).toBe('Listed windows');
  });

  it('summarises click', () => {
    const calls = [
      call('click', 'allow', 'cua-driver'),
    ];
    expect(summarise(calls)).toBe('Clicked');
  });

  it('summarises type_text', () => {
    const calls = [
      call('type_text', 'allow', 'cua-driver'),
    ];
    expect(summarise(calls)).toBe('Typed text');
  });

  it('summarises scroll', () => {
    const calls = [
      call('scroll', 'allow', 'cua-driver'),
    ];
    expect(summarise(calls)).toBe('Scrolled');
  });

  it('summarises hotkey', () => {
    const calls = [
      call('hotkey', 'allow', 'cua-driver'),
    ];
    expect(summarise(calls)).toBe('Sent hotkey');
  });

  it('summarises mixed cua and code tools', () => {
    const calls = [
      call('search_code', 'allow', 'code'),
      call('click', 'allow', 'cua-driver'),
      call('read_lines', 'allow', 'code'),
    ];
    const result = summarise(calls);
    expect(result).toContain('Searched code');
    expect(result).toContain('clicked'); // later items are lower-cased: it reads as one sentence
    expect(result).toContain('read a file');
  });
});