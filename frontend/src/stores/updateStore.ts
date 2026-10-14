/**
 * Updates, as the window holds them.
 *
 * One store behind two surfaces -- the banner and the Settings section -- so
 * pressing *Download* in one shows its progress in the other. The backend owns
 * the truth (`GET /updates/status`); this holds the last answer, the one thing
 * the window decides (a banner put off for this session), and a poll that runs
 * only while a download is under way.
 *
 * **Nothing is fetched until the person has said yes.** `start()` reads the
 * status, and asks the backend to check only when `checks` is true -- and even
 * then the backend declines if it was asked within the hour. A person who has
 * not been asked yet, or said no, causes no request at all (rule 7g, amended
 * 16 August 2026: asked once, default yes).
 */
import { create } from 'zustand';

import {
  checkForUpdates,
  fetchUpdateStatus,
  installUpdate,
  setUpdateChecks,
  startUpdateDownload,
  type UpdateStatus,
} from '@/services/updatesClient';

const POLL_MS = 1000;

interface UpdateStore {
  status: UpdateStatus | null;
  /** A sentence about the last thing that went wrong, or null. */
  message: string | null;
  busy: boolean;
  /** "Later", for this session only. */
  dismissed: boolean;
  start: () => Promise<void>;
  refresh: () => Promise<void>;
  answer: (on: boolean) => Promise<void>;
  check: () => Promise<void>;
  download: () => Promise<void>;
  install: () => Promise<void>;
  dismiss: () => void;
}

let polling: ReturnType<typeof setTimeout> | null = null;
let started = false;

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export const useUpdateStore = create<UpdateStore>((set, get) => {
  const watch = () => {
    if (polling) clearTimeout(polling);
    polling = setTimeout(async () => {
      polling = null;
      await get().refresh();
      if (get().status?.phase === 'downloading') watch();
    }, POLL_MS);
  };

  return {
    status: null,
    message: null,
    busy: false,
    dismissed: false,

    refresh: async () => {
      try {
        const status = await fetchUpdateStatus();
        set({ status, message: status.error || null });
      } catch (error) {
        set({ message: describe(error) });
      }
    },

    // Once per launch. The backend's own throttle covers a second window.
    start: async () => {
      if (started) return;
      started = true;
      await get().refresh();
      const status = get().status;
      if (status?.known && status.checks === true) {
        try {
          set({ status: await checkForUpdates(false) });
        } catch (error) {
          set({ message: describe(error) });
        }
      }
      if (get().status?.phase === 'downloading') watch();
    },

    answer: async (on) => {
      set({ busy: true, message: null });
      try {
        const status = await setUpdateChecks(on);
        set({ status, message: status.note ?? null });
        if (on) set({ status: await checkForUpdates(true) });
      } catch (error) {
        set({ message: describe(error) });
      } finally {
        set({ busy: false });
      }
    },

    check: async () => {
      set({ busy: true, message: null, dismissed: false });
      try {
        const status = await checkForUpdates(true);
        set({ status, message: status.error || null });
      } catch (error) {
        set({ message: describe(error) });
      } finally {
        set({ busy: false });
      }
    },

    download: async () => {
      set({ busy: true, message: null });
      try {
        const status = await startUpdateDownload();
        set({ status });
        watch();
      } catch (error) {
        set({ message: describe(error) });
      } finally {
        set({ busy: false });
      }
    },

    install: async () => {
      set({ busy: true, message: null });
      try {
        const result = await installUpdate();
        if (!result.ok) set({ message: result.reason ?? 'The update could not be started.' });
      } catch (error) {
        set({ message: describe(error) });
      } finally {
        set({ busy: false });
      }
    },

    dismiss: () => set({ dismissed: true }),
  };
});

/** For tests: forget that a launch check has run, and stop polling. */
export function resetUpdateStoreForTests(): void {
  started = false;
  if (polling) clearTimeout(polling);
  polling = null;
  useUpdateStore.setState({ status: null, message: null, busy: false, dismissed: false });
}
