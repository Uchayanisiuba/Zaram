/**
 * The chord the interface shows is the chord that works.
 *
 * **This exists because the two were computed in different places.**
 * `chordTokens` rendered a `meta` shortcut as "Ctrl" on Windows; `matches`
 * waited for `event.metaKey` — the physical Windows key, which the OS takes
 * before the page ever sees it. So the help overlay listed fourteen shortcuts,
 * every one of them advertised correctly, and not one of them fired. The keycap
 * was a claim about the system that the system did not honour.
 *
 * A label and a matcher agreeing is not something a type can enforce, so it is
 * enforced here: for every shortcut, on both platforms, synthesise the exact
 * keyboard event the rendered chord describes and require the matcher to
 * accept it.
 */
import { describe, it, expect } from 'vitest';
import {
  REGISTRY,
  SHIFTED_KEYS,
  chordTokens,
  matches,
  type Platform,
  type Shortcut,
} from './registry';

/** What macOS actually emits for ⌥ + letter.
 *
 *  Option is a compose key there: it does not decorate the character, it
 *  *replaces* it. Only the entries this registry needs are listed — a full
 *  table would be a second source of truth about a keyboard. */
const MAC_OPTION_COMPOSES: Record<string, string> = { c: 'ç' };

/** Build the event a keyboard would emit for a rendered chord.
 *
 *  Shift is taken from the chord *and* from the character itself — "?" is
 *  unreachable without Shift on a standard layout, whether or not the chord
 *  spells it out.
 *
 *  **`platform` is not decoration.** This helper is the only thing standing
 *  between the registry and a chord that is printed on a keycap and cannot be
 *  pressed, so it has to emit what the platform's keyboard emits rather than
 *  what the chord looks like. A Mac holding Option sends `key: "ç"` for ⌥C,
 *  and `code` is the only field that still says which key was struck — so an
 *  idealised `key: "c"` here would have passed while the real shortcut was
 *  dead on every Mac. That is the failure this file's header warns about,
 *  committed by the file itself. */
function eventFor(chord: string, platform: Platform = 'win'): KeyboardEvent {
  const parts = chord.split(' ');
  const printed = parts.pop() as string;
  const typed = printed.length === 1 ? printed.toLowerCase() : printed;
  const held = (...tokens: string[]) => tokens.some((t) => parts.includes(t));
  const altHeld = held('Alt', '⌥');

  const key =
    platform === 'mac' && altHeld && MAC_OPTION_COMPOSES[typed]
      ? MAC_OPTION_COMPOSES[typed]
      : typed;

  return new KeyboardEvent('keydown', {
    key,
    code: /^[a-z]$/.test(typed) ? `Key${typed.toUpperCase()}` : '',
    metaKey: held('⌘'),
    ctrlKey: held('Ctrl', '⌃'),
    altKey: altHeld,
    shiftKey: held('Shift', '⇧') || SHIFTED_KEYS.has(typed),
  });
}

const platforms: Platform[] = ['mac', 'win'];
const command = REGISTRY.find((s) => s.id === 'command') as Shortcut;

describe('keyboard shortcuts', () => {
  for (const platform of platforms) {
    describe(`on ${platform}`, () => {
      it('fires on the chord it prints on the keycap', () => {
        for (const shortcut of REGISTRY) {
          const chord = chordTokens(shortcut, platform);
          expect(
            matches(eventFor(chord, platform), shortcut, platform),
            `${shortcut.id} is shown as "${chord}" and does not respond to it`,
          ).toBe(true);
        }
      });

      it('prints a modifier for every shortcut that needs one', () => {
        // A bare letter would swallow typing anywhere outside a text field.
        for (const shortcut of REGISTRY) {
          if (shortcut.keys.key === '?') continue;
          expect(chordTokens(shortcut, platform).split(' ').length).toBeGreaterThan(1);
        }
      });
    });
  }

  it('takes Ctrl, not the Windows key, on Windows', () => {
    const ctrlK = new KeyboardEvent('keydown', { key: 'k', ctrlKey: true });
    const winK = new KeyboardEvent('keydown', { key: 'k', metaKey: true });
    expect(matches(ctrlK, command, 'win')).toBe(true);
    // The OS claims Win+K for itself. A shortcut that answers to it is a
    // shortcut the user cannot press.
    expect(matches(winK, command, 'win')).toBe(false);
  });

  it('takes Command, not Control, on a Mac', () => {
    const cmdK = new KeyboardEvent('keydown', { key: 'k', metaKey: true });
    const ctrlK = new KeyboardEvent('keydown', { key: 'k', ctrlKey: true });
    expect(matches(cmdK, command, 'mac')).toBe(true);
    expect(matches(ctrlK, command, 'mac')).toBe(false);
  });

  it('does not fire when an extra modifier is held', () => {
    // Ctrl+Shift+K belongs to the browser's console, not to us.
    const ctrlShiftK = new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, shiftKey: true });
    expect(matches(ctrlShiftK, command, 'win')).toBe(false);
  });

  it('leaves the reflexive OS chords — copy, paste, cut, save, open, print — alone', () => {
    /**
     * `useShortcuts` calls `preventDefault()` on any match outside a text
     * field, so claiming one of these does not merely shadow it — it deletes
     * it. Copy was claimed by Toggle Chat, and Memory, Knowledge and Activity
     * are screens whose whole job is showing facts, citations and egress rows
     * that a person will want to copy.
     *
     * Asserted against the whole registry rather than against the one chord
     * that was wrong, because the next shortcut added is the one that would
     * take Ctrl+V.
     *
     * **This test was named for Save and did not test Save.** The list held
     * `c/v/x/a/z` — copy, paste, cut, select-all, undo — while the title
     * claimed a guarantee one letter wider, and `Ctrl+S` and `Ctrl+O` were
     * meanwhile being deleted by the four orb debug shortcuts. A test that
     * reports coverage it does not have is worse than no test, because the
     * name is what the next person reads. The list is now what the name says
     * plus the rest of the reflexive set: open, save, print, find, new and
     * close.
     */
    const universal = ['c', 'v', 'x', 'a', 'z', 's', 'o', 'p', 'f', 'n', 'w'];
    for (const platform of platforms) {
      for (const key of universal) {
        const event = new KeyboardEvent('keydown', {
          key,
          code: `Key${key.toUpperCase()}`,
          ctrlKey: platform === 'win',
          metaKey: platform === 'mac',
        });
        const claimed = REGISTRY.find((s) => matches(event, s, platform));
        expect(
          claimed,
          `${claimed?.id} answers to the ${platform} Copy/Paste family key "${key}"`,
        ).toBeUndefined();
      }
    }
  });

  it('gives every shortcut a distinct chord on each platform', () => {
    for (const platform of platforms) {
      const chords = REGISTRY.map((s) => chordTokens(s, platform));
      expect(new Set(chords).size, `duplicate chord on ${platform}`).toBe(chords.length);
    }
  });
});
