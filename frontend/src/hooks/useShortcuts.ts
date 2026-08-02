import { useEffect } from 'react';
import type {
  Platform,
  Shortcut,
  ShortcutAction,
  WorkspaceId,
  OrbState,
} from '@/runtime/shortcuts/registry';
import { REGISTRY, matches } from '@/runtime/shortcuts/registry';

export interface ShortcutHandlers {
  navigate: (id: WorkspaceId) => void;
  openCommand: () => void;
  toggleChat: () => void;
  toggleDock: () => void;
  setOrb: (state: OrbState) => void;
  toggleHelp: () => void;
}

export function useShortcuts(platform: Platform, handlers: ShortcutHandlers) {
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || target?.isContentEditable) return;
      const match: Shortcut | undefined = REGISTRY.find((s) => matches(e, s, platform));
      if (!match) return;
      e.preventDefault();
      dispatch(match.action, handlers);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [platform, handlers]);
}

function dispatch(action: ShortcutAction, handlers: ShortcutHandlers): void {
  switch (action.type) {
    case 'navigate':
      handlers.navigate(action.target);
      break;
    case 'command':
      handlers.openCommand();
      break;
    case 'chat':
      handlers.toggleChat();
      break;
    case 'dock':
      handlers.toggleDock();
      break;
    case 'orb':
      handlers.setOrb(action.target);
      break;
    case 'help':
      handlers.toggleHelp();
      break;
  }
}
