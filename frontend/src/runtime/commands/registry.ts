// src/runtime/commands/registry.ts
import { useSurfaceStore } from '@/stores/surfaceStore';
import { useOrbStore } from '@/stores/orbStore';

export interface Command {
  id: string;
  label: string;
  description?: string;
  icon?: string;
  category: 'navigation' | 'action' | 'surface' | 'system';
  shortcut?: string;
  execute: () => void;
}

// This is a temporary solution. In the future, we will need a way
// to access stores from outside of React components.
const tempStoreHooks = {
  surface: useSurfaceStore,
  orb: useOrbStore,
};

export const commandRegistry: Command[] = [
  {
    id: 'open-knowledge',
    label: 'Open Knowledge',
    category: 'surface',
    execute: () => {
      const { openSurface, focusSurface, surfaces } = tempStoreHooks.surface.getState();
      const existing = surfaces.find((s) => s.type === 'knowledge');
      if (existing) {
        focusSurface(existing.id);
      } else {
        openSurface('knowledge', 'Knowledge');
      }
    },
  },
  {
    id: 'open-build',
    label: 'Open Build',
    category: 'surface',
    execute: () => {
      const { openSurface, focusSurface, surfaces } = tempStoreHooks.surface.getState();
      const existing = surfaces.find((s) => s.type === 'build');
      if (existing) {
        focusSurface(existing.id);
      } else {
        openSurface('build', 'Build');
      }
    },
  },
  {
    id: 'open-create',
    label: 'Open Create',
    category: 'surface',
    execute: () => {
      const { openSurface, focusSurface, surfaces } = tempStoreHooks.surface.getState();
      const existing = surfaces.find((s) => s.type === 'create');
      if (existing) {
        focusSurface(existing.id);
      } else {
        openSurface('create', 'Create');
      }
    },
  },
  {
    id: 'run-diagnostics',
    label: 'Run Diagnostics',
    category: 'system',
    execute: () => console.log('Running diagnostics...'),
  },
  {
    id: 'clear-memory',
    label: 'Clear Memory',
    category: 'action',
    execute: () => console.log('Clearing memory...'),
  },
];