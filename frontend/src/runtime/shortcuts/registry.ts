export type Platform = 'mac' | 'win';
// Build, Canvas and Plugins are out of scope for v1. Their surfaces are preserved
// in src/legacy/ and are not reachable from the shell.
// The canonical list. It was previously redeclared, identically, in App,
// TopNav, LeftRail, BottomDock, CommandPalette and Landing — so adding Activity
// broke in four places at once. Import it from here rather than restating it.
export type WorkspaceId =
  | 'landing'
  | 'work'
  | 'project'
  | 'memory'
  | 'knowledge'
  | 'activity'
  | 'settings';
export type OrbState = 'idle' | 'thinking' | 'speaking' | 'listening';

export type ShortcutAction =
  | { type: 'navigate'; target: WorkspaceId }
  | { type: 'command' }
  | { type: 'help' }
  | { type: 'chat' }
  | { type: 'dock' }
  | { type: 'orb'; target: OrbState };

export interface Shortcut {
  id: string;
  label: string;
  group: 'navigation' | 'orb' | 'window' | 'general';
  keys: { meta?: boolean; ctrl?: boolean; alt?: boolean; shift?: boolean; key: string };
  action: ShortcutAction;
}

export const surfaceOrder: WorkspaceId[] = [
  'landing',
  'work',
  'project',
  'memory',
  'knowledge',
  'activity',
  'settings',
];

export const surfaceLabels: Record<WorkspaceId, string> = {
  landing: 'Landing',
  work: 'Work',
  project: 'Project',
  memory: 'Memory',
  knowledge: 'Knowledge',
  activity: 'Activity',
  settings: 'Settings',
};

/** The six nodes of the orbit, in order. Landing is the shell, not a node.
 *
 *  Project sits next to Work because they are adjacent and distinct: Work is
 *  the output, Project is the organisation of it. It earned a node rather than
 *  being a filter inside Work because `project:<id>` scopes *facts* — it
 *  reaches the Spine and the plan, and a filter living inside Work cannot own
 *  something that scopes Memory. See CLAUDE.md, 10 August 2026.
 *
 *  Consumers that render navigation derive their list from this, and key their
 *  icons off `Record<WorkspaceId, …>` so the compiler names every file that
 *  needs updating when a node is added. The comment above about Activity
 *  breaking four places was written and then not acted on: TopNav, LeftRail and
 *  CommandPalette each restated the list anyway, and CommandPalette silently
 *  lost Activity as a result — it was unreachable from Ctrl K until Work was added
 *  and the restatements were removed. */
export const orbitOrder: Exclude<WorkspaceId, 'landing'>[] = [
  'work',
  'project',
  'memory',
  'knowledge',
  'activity',
  'settings',
];

export const NAV_SHORTCUTS: Shortcut[] = surfaceOrder.map((id, i) => ({
  id: `nav.${id}`,
  label: surfaceLabels[id],
  group: 'navigation',
  keys: { meta: true, key: String(i + 1) },
  action: { type: 'navigate', target: id } as const,
}));

export const REGISTRY: Shortcut[] = [
  ...NAV_SHORTCUTS,
  {
    id: 'orb.idle',
    label: 'Orb · Idle',
    group: 'orb',
    keys: { meta: true, key: 'o' },
    action: { type: 'orb', target: 'idle' },
  },
  {
    id: 'orb.listening',
    label: 'Orb · Listening',
    group: 'orb',
    keys: { meta: true, key: 'l' },
    action: { type: 'orb', target: 'listening' },
  },
  {
    id: 'orb.speaking',
    label: 'Orb · Speaking',
    group: 'orb',
    keys: { meta: true, key: 's' },
    action: { type: 'orb', target: 'speaking' },
  },
  {
    id: 'orb.thinking',
    label: 'Orb · Thinking',
    group: 'orb',
    keys: { meta: true, key: 't' },
    action: { type: 'orb', target: 'thinking' },
  },
  {
    id: 'chat',
    label: 'Toggle Chat',
    group: 'window',
    // **Not Ctrl+C.** `useShortcuts` calls `preventDefault()` on every match
    // outside a text field, so this chord was eating Copy on all six surfaces
    // — measured with a live selection. Memory, Knowledge and Activity exist
    // to show facts, citations and egress rows, and copying one of them is an
    // ordinary thing to want; a product whose pitch is that the interface
    // tells you the truth should not silently swallow the most universal
    // keystroke there is.
    //
    // Alt keeps the C mnemonic and collides with nothing: the window sets
    // `autoHideMenuBar`, so no menu claims Alt+letter, and the browser does
    // not use it either. Bare Shift+C was considered and refused — that is a
    // capital letter, not a chord, and it is one un-exempted focusable element
    // away from firing at somebody typing.
    keys: { alt: true, key: 'c' },
    action: { type: 'chat' },
  },
  {
    id: 'dock',
    label: 'Toggle Dock',
    group: 'window',
    keys: { meta: true, key: 'd' },
    action: { type: 'dock' },
  },
  {
    id: 'command',
    label: 'Command Palette',
    group: 'general',
    keys: { meta: true, key: 'k' },
    action: { type: 'command' },
  },
  {
    id: 'help',
    label: 'Shortcuts',
    group: 'general',
    keys: { key: '?' },
    action: { type: 'help' },
  },
];

/** `meta` means *the platform's primary chord key* — Command on a Mac, Control
 *  on Windows. It does not mean the physical Windows key, which the OS takes
 *  before the page sees it and which no shortcut may claim. `ctrl` is the
 *  literal Control key, distinct from `meta` only on a Mac; on Windows the two
 *  collapse onto Ctrl, which is why `chordTokens` renders both as "Ctrl". */
export function chordTokens(shortcut: Shortcut, platform: Platform): string {
  const parts: string[] = [];
  if (shortcut.keys.meta) parts.push(platform === 'mac' ? '\u2318' : 'Ctrl');
  if (shortcut.keys.ctrl) parts.push(platform === 'mac' ? '\u2303' : 'Ctrl');
  if (shortcut.keys.alt) parts.push(platform === 'mac' ? '\u2325' : 'Alt');
  if (shortcut.keys.shift) parts.push(platform === 'mac' ? '\u21e7' : 'Shift');
  parts.push(shortcut.keys.key.toUpperCase());
  return parts.join(' ');
}

/** Characters a standard layout cannot produce without Shift held. Exported so
 *  a test can synthesise the same event the keyboard would, rather than
 *  restating the set and drifting from it. */
export const SHIFTED_KEYS = new Set(['?', '!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '+', '{', '}', '|', '<', '>', '~', ':', '"']);

/** True when `event` is the physical key this shortcut names.
 *
 * **`event.key` is the character produced, not the key pressed, and Option
 * changes it.** On macOS ⌥C emits `key: "ç"` — so an Alt chord compared on
 * `event.key` is printed on the keycap, shown in the help overlay, and never
 * fires. That is the same shape as the Ctrl+K/Win+K defect recorded below:
 * the interface advertising a chord the matcher does not answer to.
 *
 * So an Alt chord on a letter is matched by physical position instead, which
 * is what the user actually pressed and is stable across layouts. Everything
 * else keeps `event.key`, because `code` would break `?` — a shifted Slash on
 * a US layout and a different key entirely elsewhere.
 */
function hitsTheKey(event: KeyboardEvent, shortcut: Shortcut): boolean {
  const { alt, key } = shortcut.keys;
  if (alt && /^[a-z]$/i.test(key)) {
    // `code` is absent on a synthetic event that did not set it; falling back
    // keeps such an event matchable rather than silently unmatchable.
    return event.code ? event.code === `Key${key.toUpperCase()}` : event.key === key;
  }
  return event.key === key;
}

export function matches(event: KeyboardEvent, shortcut: Shortcut, platform: Platform): boolean {
  const { meta, ctrl, alt, shift, key } = shortcut.keys;
  if (!hitsTheKey(event, shortcut)) return false;

  const needsShift = !!shift || SHIFTED_KEYS.has(key);
  if (event.shiftKey !== needsShift) return false;
  if (!!alt !== event.altKey) return false;

  if (platform === 'mac') {
    if (!!meta !== event.metaKey) return false;
    if (!!ctrl !== event.ctrlKey) return false;
  } else {
    // Windows: `meta` and `ctrl` both resolve to Ctrl, exactly as chordTokens
    // renders them. This branch used to require `event.metaKey` for a `meta`
    // shortcut, so the help overlay advertised "Ctrl K" while the matcher
    // waited for Win+K — a chord the OS intercepts. Every registry shortcut
    // was unreachable on Windows and the interface said otherwise.
    if ((!!meta || !!ctrl) !== event.ctrlKey) return false;
    // The Windows key is never part of a chord here, so holding it is not a
    // near-miss to be forgiven: Win+K must not open the palette.
    if (event.metaKey) return false;
  }
  return true;
}

export function detectPlatform(): Platform {
  if (typeof navigator === 'undefined') return 'win';
  return /mac/i.test(navigator.userAgent) ? 'mac' : 'win';
}
