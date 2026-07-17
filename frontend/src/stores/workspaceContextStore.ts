// frontend/src/stores/workspaceContextStore.ts
//
// Sprint 2.2 — Workspace-Aware Conversation store.
//
// Connects the existing Workspace Runtime to the Developer Preview. It is an
// event-driven observer: it subscribes to Workspace Runtime events through the
// existing runtime interface (desktop.workspace) and updates reactively. It does
// NOT poll and does NOT import fs / node:fs / renderer / orb / embodiment /
// electron / three / webgpu. Live updates arrive via the runtime's pub/sub.

import { create } from 'zustand'
import { desktop } from '@/desktop/desktop-bridge'
import {
  isIndexing,
  type WorkspaceSnapshot,
} from '@/lib/workspaceConversation'

export interface WorkspaceContextEvent {
  eventId: number
  timestamp: number
  type: string
  data: Record<string, unknown>
}

interface WorkspaceContextState {
  snapshot: WorkspaceSnapshot | null
  events: WorkspaceContextEvent[]
  advancedMode: boolean
  indexing: boolean
  hasWorkspace: boolean

  setSnapshot: (snapshot: WorkspaceSnapshot | null) => void
  ingestEvent: (event: WorkspaceContextEvent) => void
  refreshSnapshot: () => Promise<void>
  setAdvancedMode: (value: boolean) => void
  subscribeToWorkspace: () => () => void
  reset: () => void
}

const MAX_EVENTS = 200

export const useWorkspaceContextStore = create<WorkspaceContextState>(
  (set, get) => ({
    snapshot: null,
    events: [],
    advancedMode: false,
    indexing: false,
    hasWorkspace: false,

    setSnapshot: (snapshot) =>
      set({
        snapshot,
        hasWorkspace: Boolean(snapshot && snapshot.workspace && snapshot.workspace !== 'root'),
      }),

    ingestEvent: (event) =>
      set((state) => {
        const events = [...state.events, event].slice(-MAX_EVENTS)
        return {
          events,
          indexing: isIndexing(events),
        }
      }),

    refreshSnapshot: async () => {
      const snapshot = (await desktop.workspace.getSnapshot()) as
        | WorkspaceSnapshot
        | null
        if (snapshot) {
          get().setSnapshot(snapshot)
        }
      },

    setAdvancedMode: (value) => set({ advancedMode: value }),

    subscribeToWorkspace: () => {
      // Seed with the current snapshot (no polling; single read on mount).
      void get().refreshSnapshot()

      const unsub = desktop.workspace.onEvent((event: any) => {
        const evt: WorkspaceContextEvent = {
          eventId: event?.eventId ?? Date.now(),
          timestamp: event?.timestamp ?? Date.now(),
          type: event?.type ?? 'unknown',
          data: event?.data ?? {},
        }
        get().ingestEvent(evt)

        // Live snapshot refresh on every snapshot-bearing event.
        if (
          evt.type === 'workspace.snapshot_created' ||
          evt.type === 'workspace.changed' ||
          evt.type === 'workspace.discovered' ||
          evt.type === 'workspace.scan_completed' ||
          evt.type === 'workspace.project_added'
        ) {
          void get().refreshSnapshot()
        }
      })

      return unsub
    },

    reset: () =>
      set({ snapshot: null, events: [], indexing: false, hasWorkspace: false }),
  })
)
