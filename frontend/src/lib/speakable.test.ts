/**
 * @vitest-environment node
 *
 * What Kokoro is handed, as against what the screen shows.
 *
 * Reported by the maintainer on 3 September 2026: Zaram reads code aloud and
 * reads punctuation. The transform is small; the property that matters is not.
 * `speechStore` cleans the *accumulated* reply on every token and keeps a
 * character cursor into the result, so a rule whose output changes once more
 * text arrives makes speech repeat itself or skip a sentence — and it would do
 * that only under streaming, which no test of the finished text can see. The
 * last block here is that property, asserted character by character.
 */
import { describe, it, expect } from 'vitest';
import { speakableText } from './speakable';

describe('what is said, and what is only shown', () => {
  it('does not read a code block', () => {
    const spoken = speakableText(
      'Here is the fix.\n\n```python\ndef total(rows):\n    return sum(r.amount for r in rows)\n```\n\nRun it against the ledger.',
    );

    expect(spoken).not.toContain('def total');
    expect(spoken).not.toContain('return sum');
    expect(spoken).toContain('Here is the fix.');
    expect(spoken).toContain('Run it against the ledger.');
  });

  it('does not read a block that is still arriving', () => {
    // The half-written state, which is what the streaming path actually sees.
    const spoken = speakableText('Here is the fix.\n\n```python\ndef total(rows):\n    return su');

    expect(spoken).not.toContain('def total');
    expect(spoken).toContain('Here is the fix.');
  });

  it('keeps what inline code names, and drops the backticks', () => {
    const spoken = speakableText('Open `main.py` and change `--strictPort`.');

    expect(spoken).toContain('main.py');
    expect(spoken).toContain('--strictPort');
    expect(spoken).not.toContain('`');
  });

  it('says the words of a heading and not its hashes', () => {
    expect(speakableText('## What changed\n\nTwo things.')).toBe(
      'What changed\n\nTwo things.',
    );
  });

  it('says an emphasised word without its asterisks', () => {
    expect(speakableText('That is **not** what the clause says.').replace(/\s+/g, ' ')).toBe(
      'That is not what the clause says.',
    );
  });

  it('says a list item without its bullet', () => {
    const spoken = speakableText('- Invoice 4102\n- Invoice 4103');
    expect(spoken).toBe('Invoice 4102\nInvoice 4103');
  });

  it('says a link by its words rather than its address', () => {
    const spoken = speakableText('See [the terms](https://example.com/terms/2026) for the date.');

    expect(spoken).toContain('the terms');
    expect(spoken).not.toContain('example.com');
  });

  it('does not spell out a bare address', () => {
    expect(speakableText('It is at https://example.com/a/b?c=d now.')).not.toContain(
      'example.com',
    );
  });

  it('reads a snake_case name as words rather than as one', () => {
    expect(speakableText('Check user_settings.')).toBe('Check user settings.');
  });

  it('leaves sentence punctuation alone, because that is prosody', () => {
    const spoken = speakableText('It is due, unpaid, on the ninth; chase it. Will you?');
    expect(spoken).toBe('It is due, unpaid, on the ninth; chase it. Will you?');
  });

  it('still strips citation markers, which is where this function started', () => {
    expect(speakableText('The rate is £450 [M1] a day [S2].')).toBe(
      'The rate is £450 a day.',
    );
  });
});

describe('the property streaming depends on', () => {
  /**
   * The cleaned form of a prefix must be a prefix of the cleaned form of the
   * whole. `speechStore` advances a character cursor over this text and never
   * looks back, so anything that changes behind the cursor is either spoken
   * twice or never spoken at all.
   */
  const stableWhileStreaming = (reply: string) => {
    const whole = speakableText(reply);
    for (let i = 1; i <= reply.length; i++) {
      const partial = speakableText(reply.slice(0, i));
      expect(
        whole.startsWith(partial),
        `after ${i} characters the spoken text was not a prefix of the finished one:\n` +
          `  partial: ${JSON.stringify(partial)}\n` +
          `  whole:   ${JSON.stringify(whole.slice(0, partial.length + 20))}`,
      ).toBe(true);
    }
  };

  it('holds across a reply with a code block in the middle of it', () => {
    stableWhileStreaming('Here is the fix.\n\n```py\nx = 1\n```\n\nRun it.');
  });

  it('holds across headings, bullets and emphasis', () => {
    stableWhileStreaming('## Two things\n\n- The **rate** is set.\n- The date is not.\n');
  });

  it('holds across a link', () => {
    stableWhileStreaming('See [the terms](https://example.com) today.');
  });
});
