/**
 * Shift+Space, and the two things it must not do.
 *
 * The chord itself is round-tripped by `registry.test.ts` like every other one.
 * What is asserted here is what makes *this* chord different from the rest of
 * the registry: it opens a microphone. Every other shortcut moves the interface
 * around, so a misfire costs a surface change; a misfire here costs a recording
 * the user did not ask for.
 *
 * So: it must never fire while somebody is writing, and it must be its own
 * action rather than a variant of "open the conversation" — a keystroke pressed
 * to *read* a conversation must not start listening.
 */
import { describe, expect, it } from 'vitest';

import { REGISTRY, matches, type Platform, type Shortcut } from './registry';

const voice = REGISTRY.find((s) => s.id === 'voice') as Shortcut;
const platforms: Platform[] = ['mac', 'win'];

const press = (over: Partial<KeyboardEventInit> = {}) =>
  new KeyboardEvent('keydown', { key: ' ', shiftKey: true, ...over });

describe('the voice chord', () => {
  it('exists, and asks for its own action', () => {
    // Not `{ type: 'chat' }` with a flag. Folding voice into the chat toggle
    // would mean the keystroke somebody presses to read their conversation
    // also turns the microphone on.
    expect(voice).toBeDefined();
    expect(voice.action).toEqual({ type: 'voice' });
  });

  it('is Shift and Space, not Space alone', () => {
    // Bare Space is the most-pressed key there is and it scrolls. `useShortcuts`
    // calls `preventDefault()` on every match outside a text field, so claiming
    // it would not shadow scrolling — it would delete it, on every surface.
    expect(voice.keys).toMatchObject({ shift: true, key: ' ' });
  });

  it.each(platforms)('fires on %s', (platform) => {
    expect(matches(press(), voice, platform)).toBe(true);
  });

  it.each(platforms)('does not fire on Space alone on %s', (platform) => {
    expect(matches(press({ shiftKey: false }), voice, platform)).toBe(false);
  });

  it.each(platforms)('does not fire when another modifier is held on %s', (platform) => {
    // Ctrl+Shift+Space and Alt+Shift+Space belong to whatever else claims them.
    expect(matches(press({ ctrlKey: true }), voice, platform)).toBe(false);
    expect(matches(press({ altKey: true }), voice, platform)).toBe(false);
  });

  it('is not claimed by any other shortcut', () => {
    for (const platform of platforms) {
      const claimants = REGISTRY.filter((s) => matches(press(), s, platform));
      expect(claimants.map((s) => s.id)).toEqual(['voice']);
    }
  });

  it('leaves ordinary Space to the page', () => {
    // Nothing in the registry may answer to a bare Space, on either platform.
    for (const platform of platforms) {
      const claimed = REGISTRY.find((s) => matches(press({ shiftKey: false }), s, platform));
      expect(claimed?.id, 'something answers to a bare Space').toBeUndefined();
    }
  });
});
