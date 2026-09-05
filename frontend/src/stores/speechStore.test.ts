/**
 * What the user is told when speech cannot run.
 *
 * `CLAUDE.md`: a disabled capability is visible, not silent — and the OCR
 * extra sets the standard for how, by quoting "pip install zaram[ingest]
 * (321 MB, one time)" rather than "OCR is unavailable". Naming the fix without
 * naming its cost is not a choice somebody on metered data can make.
 *
 * The speech path had the comment and not the string: directly above the
 * message was a note saying it was reported "so the UI can name the fix and
 * its size the way the OCR extra does", and the message said only "Speech is
 * not installed." A comment describing a guarantee the code does not give is
 * the same defect as a test named for one it does not check.
 *
 * These assert the *properties* — a command, a size — rather than the wording,
 * so rephrasing stays free and hollowing it out does not.
 */

import { describe, it, expect } from 'vitest';

import { SPEECH_NOT_INSTALLED } from './speechStore';

describe('the speech-unavailable message', () => {
  it('names the command that fixes it', () => {
    expect(SPEECH_NOT_INSTALLED).toContain('pip install');
    expect(SPEECH_NOT_INSTALLED).toContain('requirements-voice.txt');
  });

  it('names what the fix costs', () => {
    // A number followed by a unit, anywhere in the sentence. The size is the
    // half that decides on a metered connection, and it is the half that was
    // missing.
    expect(SPEECH_NOT_INSTALLED).toMatch(/\d+\s?(MB|GB)/);
  });

  it('says speech is not installed rather than that it failed', () => {
    // "Speech failed (503)." is what the other branch says, and it is the
    // wrong claim here: nothing failed, something was never installed. The
    // difference is whether the reader looks for a bug or runs a command.
    expect(SPEECH_NOT_INSTALLED.toLowerCase()).toContain('not installed');
    expect(SPEECH_NOT_INSTALLED.toLowerCase()).not.toContain('failed');
  });
});
