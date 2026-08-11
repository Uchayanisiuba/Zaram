/**
 * @vitest-environment node
 *
 * Where a reply is cut for speech.
 *
 * The split exists to stop time-to-first-sound scaling with reply length —
 * Kokoro on CPU runs at roughly real time, so synthesising a whole answer
 * before playing any of it makes the user wait out the entire answer first.
 *
 * These assert the two ways splitting makes things *worse* rather than better,
 * because those are the cases that would ship silently: a figure cut in half
 * mid-number, and chunks so small the per-request overhead costs more than the
 * audio they buy.
 */
import { describe, it, expect } from 'vitest';
import { splitIntoUtterances } from './utterances';

const words = (parts: string[]) => parts.join(' ').replace(/\s+/g, ' ').trim();

describe('splitting a reply for speech', () => {
  it('cuts at sentence boundaries', () => {
    const parts = splitIntoUtterances(
      'The invoice is ready to send. Payment falls due on the ninth of September.',
    );

    expect(parts).toHaveLength(2);
    expect(parts[0]).toBe('The invoice is ready to send.');
  });

  it('never loses or reorders words', () => {
    // The listener hears the reply, not the chunks. Anything dropped here is
    // dropped from what Zaram said.
    const text =
      'The invoice is ready. It totals one thousand four hundred pounds. Payment is due in thirty days.';

    expect(words(splitIntoUtterances(text))).toBe(words([text]));
  });

  it('does not split inside a figure', () => {
    // "1,470." then "50" is spoken as two utterances with a pause through the
    // middle of the number, and a figure on an invoice is the one thing that
    // must not be garbled.
    const parts = splitIntoUtterances('The total is 1,470.50 and it is due on the ninth.');

    expect(parts).toHaveLength(1);
    expect(parts[0]).toContain('1,470.50');
  });

  it('does not split on a common abbreviation', () => {
    const parts = splitIntoUtterances('Send it to Dr. Adeyemi before the deadline arrives.');

    expect(parts).toHaveLength(1);
  });

  it('does not split on an initial', () => {
    const parts = splitIntoUtterances('The client is J. Okafor and the rate is agreed.');

    expect(parts).toHaveLength(1);
  });

  it('merges a fragment too small to be worth a request', () => {
    // Every chunk costs a round trip and a model call. "Done." spends all of
    // that to buy a third of a second of audio.
    const parts = splitIntoUtterances('Done. The invoice has been written and saved to your folder.');

    expect(parts).toHaveLength(1);
    expect(parts[0]).toContain('Done.');
  });

  it('merges a short trailing piece backwards', () => {
    const parts = splitIntoUtterances(
      'The invoice has been written and saved to your output folder. Thanks.',
    );

    expect(parts).toHaveLength(1);
  });

  it('breaks a very long sentence at a clause', () => {
    // One chunk long enough to wait for is the original problem again. A pause
    // at a comma sounds intended; a pause mid-phrase does not.
    const long =
      'The invoice covers three design days at the agreed rate, ' +
      'the revisions we discussed on the call last week, ' +
      'the additional artwork you asked for afterwards, ' +
      'the courier charge for the printed proofs you wanted sent over, ' +
      'and the licensing note that we agreed would be attached to the final delivery.';

    expect(long.length).toBeGreaterThan(240); // or this is not the case it claims to be

    const parts = splitIntoUtterances(long);

    expect(parts.length).toBeGreaterThan(1);
    expect(words(parts)).toBe(words([long]));
    expect(Math.max(...parts.map((p) => p.length))).toBeLessThanOrEqual(260);
  });

  it('treats a line break as a boundary', () => {
    const parts = splitIntoUtterances(
      'Here is what I found in your files\nThe rate you agreed was four hundred and fifty',
    );

    expect(parts).toHaveLength(2);
  });

  it('says nothing for nothing', () => {
    expect(splitIntoUtterances('')).toEqual([]);
    expect(splitIntoUtterances('   ')).toEqual([]);
  });

  it('handles a reply with no terminal punctuation', () => {
    expect(splitIntoUtterances('the invoice is ready to send')).toEqual([
      'the invoice is ready to send',
    ]);
  });

  it('keeps a closing quote with the sentence it ends', () => {
    const parts = splitIntoUtterances(
      'They wrote "the payment is on its way." I have not seen it arrive yet.',
    );

    expect(parts[0]).toContain('way."');
    expect(parts[1]).not.toMatch(/^["”]/);
  });
});
