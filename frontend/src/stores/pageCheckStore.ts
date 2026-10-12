/**
 * A page a reply wrote is run before the person has to.
 *
 * 5 October 2026: the resident model wrote a game whose start-up froze the
 * window, and the person was the first to run it. An agent harness running the
 * same model would have run it, seen the freeze, and fixed it before showing
 * anything. This is that step, in three parts that each answer to the person:
 *
 * * **Run it** -- the backend loads the page in a throwaway browser with no
 *   route to any host and reports a hang, an error, or a clean start
 *   (`core/page_check.py`).
 * * **If it did not work, ask for a fix -- at most twice.** Each is a visible
 *   message in the conversation, worded as Zaram's own so nobody mistakes it
 *   for something they typed. Two, because a model that cannot fix a page in
 *   two attempts needs the person, and a third attempt is the loop the guard
 *   exists to refuse. After that the failure is shown, not retried.
 * * **Say so, always.** Each reply carries a line: running, ran clean, asked
 *   for a fix (try 1 of 2), still not working, or could not be checked and why.
 *   A check that failed silently, or passed without having run, would be worse
 *   than none.
 *
 * Off switch: `enabled`, remembered. It runs a hidden browser for a few
 * seconds after a page reply and may send the model a second message, so it is
 * the person's to turn off, from the line that reports it.
 */
import { create } from 'zustand';
import { stuckLoopIn } from '@/lib/appFiles';
import { checkFailedRequest } from '@/lib/askAboutPage';
import { asFiles, asReply } from '@/lib/pageEdits';
import { buildFrameDoc } from '@/lib/previewFrame';
import { findStuckLoop } from '@/lib/previewableCode';
import { idsNamedIn, pictureMapFor, pictureNotes } from '@/lib/pagePictures';
import { pageForTurn, startersNamedIn, type ReplyPage } from '@/lib/replyPage';
import { checkPage } from '@/services/pageCheckClient';
import { useChatStore } from '@/stores/chatStore';
import { usePictureStore } from '@/stores/pictureStore';
import { blockPhotoDescriptions, photoNotes, withPhotos } from '@/lib/pagePhotos';
import { usePhotoStore } from '@/stores/photoStore';
import { useStarterStore } from '@/stores/starterStore';

/** Fixes asked for automatically, in a row, before the person is handed the failure. */
export const MAX_AUTO_FIXES = 2;

const STORAGE_KEY = 'zaram.pageCheck';

export type CheckStatus = 'checking' | 'clean' | 'fixing' | 'failed' | 'gave-up' | 'unchecked';

export interface PageCheckState {
  status: CheckStatus;
  /** One plain sentence: the first problem, or why it was not checked. */
  note: string;
  /** Which automatic fix this is, when `status` is `fixing`. */
  attempt: number;
  /** Seconds the page held still at start-up, when that was worth saying. */
  slowSeconds: number;
  /** Loops Zaram put a missing `++` back into, said under the reply. */
  repaired?: string[];
  /** The tested starting point the page was built on, if any. */
  starter?: string;
  /** Plain sentences about the person's pictures in the page: one that is no
   *  longer attached, or a reference to a picture the page does not contain. */
  pictures?: string[];
}

/** The page a reply stands for, with any starting point it names fetched
 *  first. Resolved against the conversation so changes apply to the page
 *  before them; a reply not in the conversation is read on its own. */
async function pageOf(reply: string): Promise<ReplyPage | null> {
  const turns = useChatStore.getState().messages;
  let index = -1;
  for (let i = turns.length - 1; i >= 0; i--) {
    if (turns[i].role === 'assistant' && turns[i].text === reply) {
      index = i;
      break;
    }
  }
  if (index < 0) return pageForTurn([{ role: 'assistant', text: reply }], 0, useStarterStore.getState().codes);
  await useStarterStore.getState().ensure(startersNamedIn(turns.slice(0, index + 1)));
  // The person's attached pictures this reply names are fetched first, so the
  // page is checked with them in -- the page the preview will run.
  const pictureStore = usePictureStore.getState();
  const chat = useChatStore.getState();
  await pictureStore.ensure(chat.sessionId, idsNamedIn(turns, index, turns[index].text), chat.conversationId);
  const pictures = pictureMapFor(turns, index, usePictureStore.getState().held);
  const page = pageForTurn(turns, index, useStarterStore.getState().codes, pictures);
  // And the photographs it describes, looked up first for the same reason. The
  // first search waits for the person's answer, so the check waits with it.
  const descriptions = page ? blockPhotoDescriptions(page) : [];
  if (!page || !descriptions.length) return page;
  const asked = turns.slice(0, index).reverse().find((t) => t.role === 'user');
  await usePhotoStore.getState().ensure(descriptions, asked?.text ?? '');
  return withPhotos(page, usePhotoStore.getState().found);
}

interface PageCheckStore {
  byReply: Record<string, PageCheckState>;
  enabled: boolean;
  setEnabled: (on: boolean) => void;
  /** Check the page in `reply`, once. Does nothing for a reply with no page,
   *  one already checked, or when switched off. */
  check: (reply: string, question: string) => Promise<void>;
}

/** The same reply text always gets the same key; nothing else needs an id. */
export function replyKey(text: string): string {
  let h = 5381;
  for (let i = 0; i < text.length; i++) h = ((h << 5) + h + text.charCodeAt(i)) | 0;
  return `${text.length}:${h >>> 0}`;
}

function readEnabled(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) !== 'off';
  } catch {
    return true;
  }
}

/** Fixes asked for since the last page that worked. Module-level: it is the
 *  state of one run of fixes, not something to render. */
let chain = 0;

export const usePageCheckStore = create<PageCheckStore>((set, get) => {
  const put = (key: string, state: PageCheckState) =>
    set((s) => ({ byReply: { ...s.byReply, [key]: state } }));

  return {
    byReply: {},
    enabled: readEnabled(),

    setEnabled: (on) => {
      try {
        window.localStorage.setItem(STORAGE_KEY, on ? 'on' : 'off');
      } catch {
        /* the choice holds for this session */
      }
      set({ enabled: on });
    },

    check: async (reply, question) => {
      if (!get().enabled) return;
      const block = await pageOf(reply);
      // SVG is a picture, not a program: nothing to start, nothing to hang.
      if (!block || block.language !== 'html') return;
      // **A whole page or an app, never a snippet.** An answer to "how do I
      // centre a div" carries a fragment that was never meant to run alone; a
      // fragment that throws must not send the model a fix nobody asked for,
      // which costs minutes on a local model and tokens on a cloud key.
      if (!block.files && !/<!doctype|<html[\s>]|<body[\s>]/i.test(block.code)) return;
      const key = replyKey(reply);
      if (get().byReply[key]) return;
      const notes = [...pictureNotes(block), ...photoNotes(block)];
      const said = {
        repaired: block.repaired ?? [],
        starter: block.edited?.starter ?? '',
        ...(notes.length ? { pictures: notes } : {}),
      };
      put(key, { status: 'checking', note: '', attempt: 0, slowSeconds: 0, ...said });

      // The one failure that is certain by reading the source needs no browser.
      const stuck = block.files ? stuckLoopIn(block.files, findStuckLoop) : findStuckLoop(block.code);
      const missed = block.edited?.failed ?? [];
      let problems: string[];
      let seconds = 0;
      if (missed.length) {
        // A change that matched nothing leaves the page half-made; running it
        // would report the half, not the cause.
        problems = [
          ...missed,
          'Copy each SEARCH part exactly from the page as it stands now, or write that file out in full.',
        ];
      } else if (stuck) {
        const where = 'file' in stuck && stuck.file ? `${stuck.file}, line ${stuck.line}` : `line ${stuck.line}`;
        problems = [
          `${where}: \`${stuck.text}\` never changes its counter, so the page freezes before it draws anything. ` +
            'Check every loop in the page for the same mistake.',
        ];
      } else {
        const verdict = await checkPage(await buildFrameDoc(block));
        if (!verdict.checked) {
          put(key, { status: 'unchecked', note: verdict.note, attempt: 0, slowSeconds: 0, ...said });
          return;
        }
        if (verdict.ok) {
          chain = 0;
          put(key, {
            status: 'clean',
            note: '',
            attempt: 0,
            slowSeconds: verdict.blockedSeconds >= 3 ? verdict.blockedSeconds : 0,
            ...said,
          });
          return;
        }
        problems = verdict.problems;
        seconds = verdict.blockedSeconds;
      }

      const first = problems[0] ?? 'the page did not work';
      if (chain >= MAX_AUTO_FIXES) {
        chain = 0;
        put(key, { status: 'gave-up', note: first, attempt: MAX_AUTO_FIXES, slowSeconds: seconds, ...said });
        return;
      }
      // Only while this reply is still the last word. If the person has asked
      // something since -- the check takes seconds -- a fix arriving now would
      // be out of place, and `send` refuses while a reply streams, so the line
      // would claim a request that was never made.
      const chat = useChatStore.getState();
      const latest = chat.messages[chat.messages.length - 1];
      if (chat.isStreaming || !latest || latest.role !== 'assistant' || latest.text !== reply) {
        put(key, { status: 'failed', note: first, attempt: 0, slowSeconds: seconds, ...said });
        return;
      }
      chain += 1;
      put(key, { status: 'fixing', note: first, attempt: chain, slowSeconds: seconds, ...said });
      // The model is shown the page as it now stands -- its edits applied, its
      // loops mended -- because its SEARCH lines have to match that, not the
      // reply that described the changes.
      const asItStands = block.edited || block.repaired ? asReply(block.files ?? asFiles(block.code)) : reply;
      await chat.send(checkFailedRequest(problems, Boolean(block.files)), { revise: { question, reply: asItStands } });
    },
  };
});
