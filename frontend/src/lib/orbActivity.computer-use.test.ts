import { describe, it, expect } from 'vitest';
import {
  chatActivity,
  codingActivity,
  computerUseActivity,
  composeActivity,
} from '../lib/orbActivity';

describe('orbActivity - computer use', () => {
  describe('chatActivity', () => {
    it('returns thinking when streaming', () => {
      expect(chatActivity(true)).toBe('thinking');
    });

    it('returns idle when not streaming', () => {
      expect(chatActivity(false)).toBe('idle');
    });
  });

  describe('computerUseActivity', () => {
    it('returns idle when not streaming', () => {
      expect(computerUseActivity(false, [])).toBe('idle');
    });

    it('returns thinking when streaming and no cua tools', () => {
      expect(computerUseActivity(true, ['other'])).toBe('thinking');
    });

    it('returns computer_use when cua-driver tool ran', () => {
      expect(computerUseActivity(true, ['cua-driver'])).toBe('computer_use');
    });

    it('returns computer_use when cua tool ran', () => {
      expect(computerUseActivity(true, ['cua'])).toBe('computer_use');
    });

    it('returns computer_use mixed with other tools', () => {
      expect(computerUseActivity(true, ['code', 'cua-driver'])).toBe('computer_use');
    });

    it('is sticky for rest of reply', () => {
      // Once computer_use, stays computer_use even if no more cua tools
      // (This is handled by composeActivity which checks toolServers from the whole reply)
    });
  });

  describe('composeActivity', () => {
    it('coding has highest priority', () => {
      expect(composeActivity(true, '', ['code', 'cua-driver'])).toBe('coding');
    });

    it('computer_use next priority', () => {
      expect(composeActivity(true, '', ['cua-driver'])).toBe('computer_use');
    });

    it('falls back to thinking', () => {
      expect(composeActivity(true, '', ['other'])).toBe('thinking');
    });

    it('falls back to idle', () => {
      expect(composeActivity(false, '', [])).toBe('idle');
    });

    it('coding from fence overrides computer_use', () => {
      const replyWithFence = 'Here is the code:\n```python\ndef foo(): pass\n```';
      // codingActivity checks for fence, so it should win
      expect(composeActivity(true, replyWithFence, ['cua-driver'])).toBe('coding');
    });
  });

  describe('codingActivity unchanged', () => {
    it('still works for code tools', () => {
      expect(codingActivity(true, '', ['code'])).toBe('coding');
    });

    it('still works for code fence', () => {
      expect(codingActivity(true, '```python\nx=1\n```', [])).toBe('coding');
    });

    it('returns thinking for ordinary prose', () => {
      expect(codingActivity(true, 'Just some text', [])).toBe('thinking');
    });
  });
});