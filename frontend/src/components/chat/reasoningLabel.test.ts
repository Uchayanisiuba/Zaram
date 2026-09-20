/**
 * The collapsed thinking line is the model's own words, and it moves.
 */
import { describe, it, expect } from 'vitest';
import { clip, latestThought, reasoningLabel, MAX_LABEL } from './reasoningLabel';

describe('latestThought', () => {
  it('is the first sentence of the latest paragraph', () => {
    const text =
      'Okay, the user wants dark mode. That means a theme store.\n\n' +
      'The reducer lives in store.ts. I should read it first. Then the CSS.';
    expect(latestThought(text)).toBe('The reducer lives in store.ts.');
  });

  it('takes a paragraph still being written whole, so the line moves', () => {
    expect(latestThought('First thought.\n\nNow checking whether the')).toBe(
      'Now checking whether the',
    );
  });

  it('ignores blank paragraphs and collapses whitespace', () => {
    expect(latestThought('A.\n\n\n   \n\nB   is\n here.  ')).toBe('B is here.');
  });

  it('is empty for nothing', () => {
    expect(latestThought('')).toBe('');
    expect(latestThought('\n\n')).toBe('');
  });
});

describe('reasoningLabel', () => {
  it('prefers the checklist item the model is doing', () => {
    expect(reasoningLabel('Some long thought here.', 'Read the store')).toBe('Read the store');
  });

  it('falls back to the thought when there is no item', () => {
    expect(reasoningLabel('Some thought here.', '')).toBe('Some thought here.');
    expect(reasoningLabel('Some thought here.', null)).toBe('Some thought here.');
  });
});

describe('clip', () => {
  it('leaves a short line alone', () => {
    expect(clip('short')).toBe('short');
  });

  it('cuts at a word, not inside one, and never beyond the limit', () => {
    const long = 'word '.repeat(40).trim();
    const out = clip(long);
    expect(out.endsWith('…')).toBe(true);
    expect(out.length).toBeLessThanOrEqual(MAX_LABEL + 1);
    expect(out.slice(0, -1).endsWith('word')).toBe(true);
  });

  it('drops a trailing comma before the ellipsis', () => {
    const line = 'a'.repeat(70) + ', and then something else that goes on';
    expect(clip(line).endsWith(',…')).toBe(false);
  });
});
