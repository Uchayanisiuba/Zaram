export type Platform = 'mac' | 'win';
// Build, Canvas and Plugins are out of scope for v1. Their surfaces are preserved
// in src/legacy/ and are not reachable from the shell.
// The canonical list. It was previously redeclared, identically, in App,
// TopNav, LeftRail, BottomDock, CommandPalette and Landing — so adding Activity
// broke in four places at once. Import it from here rather than restating it.
export type WorkspaceId =
  | 'landing'
  | 'work'
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
  'memory',
  'knowledge',
  'activity',
  'settings',
];

export const surfaceLabels: Record<WorkspaceId, string> = {
  landing: 'Landing',
  work: 'Work',
  memory: 'Memory',
  knowledge: 'Knowledge',
  activity: 'Activity',
  settings: 'Settings',
};

/** The five nodes of the orbit, in order. Landing is the shell, not a node.
 *
 *  Consumers that render navigation derive their list from this, and key their
 *  icons off `Record<WorkspaceId, …>` so the compiler names every file that
 *  needs updating when a node is added. The comment above about Activity
 *  breaking four places was written and then not acted on: TopNav, LeftRail and
 *  CommandPalette each restated the list anyway, and CommandPalette silently
 *  lost Activity as a result — it was unreachable from ⌘K until Work was added
 *  and the restatements were removed. */
export const orbitOrder: Exclude<WorkspaceId, 'landing'>[] = [
  'work',
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
    keys: { meta: true, key: 'c' },
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

export function chordTokens(shortcut: Shortcut, platform: Platform): string {
  const parts: string[] = [];
  if (shortcut.keys.meta) parts.push(platform === 'mac' ? '\u2318' : 'Ctrl');
  if (shortcut.keys.ctrl) parts.push(platform === 'mac' ? '\u2303' : 'Ctrl');
  if (shortcut.keys.alt) parts.push(platform === 'mac' ? '\u2325' : 'Alt');
  if (shortcut.keys.shift) parts.push(platform === 'mac' ? '\u21e7' : 'Shift');
  parts.push(shortcut.keys.key.toUpperCase());
  return parts.join(' ');
}

const SHIFTED_KEYS = new Set(['?', '!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '+', '{', '}', '|', '<', '>', '~', ':', '"']);

export function matches(event: KeyboardEvent, shortcut: Shortcut, platform: Platform): boolean {
  const { meta, ctrl, alt, shift, key } = shortcut.keys;
  if (event.key !== key) return false;

  const needsShift = !!shift || SHIFTED_KEYS.has(key);
  if (event.shiftKey !== needsShift) return false;
  if (!!alt !== event.altKey) return false;

  if (platform === 'mac') {
    if (!!meta !== event.metaKey) return false;
    if (!!ctrl !== event.ctrlKey) return false;
  } else {
    if (!!ctrl !== event.ctrlKey) return false;
    if (!!meta !== event.metaKey) return false;
  }
  return true;
}

export function detectPlatform(): Platform {
  if (typeof navigator === 'undefined') return 'win';
  return /mac/i.test(navigator.userAgent) ? 'mac' : 'win';
}
