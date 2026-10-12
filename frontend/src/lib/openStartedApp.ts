/**
 * Open an app Zaram just started in Zaram's own browser pane.
 *
 * The maintainer, 11 October 2026: *"when Zaram is building an app, instead of
 * just giving the user a link to the localhost and telling the user to open it
 * in the browser, it actually opens the localhost."* The pane existed and
 * opened from the address on a card; nothing opened it when a *reply* started
 * the server, so the person was handed a link to press.
 *
 * Four decisions, none of them obvious from the call site:
 *
 * * **Only a call that completed live.** This is called from the stream
 *   handler as the tool call arrives -- the same discipline as `apply` on a
 *   settings call -- and never from the stored message, so opening an old
 *   conversation does not start a browser for every app in its history
 *   (`hooks/usePageCheckOnReply` draws the same line for the page check).
 * * **Only Zaram's own code pack, only a loopback address.** The tool's name
 *   is a string a stranger's server can also use; the address is text a model
 *   wrote. A remote URL is never opened on anyone's behalf here -- that is
 *   browsing, which has its own rules.
 * * **Only where there is a pane.** Without a desktop host the fallback would
 *   be a system-browser tab opened with no gesture behind it, which a browser
 *   blocks and a person did not ask for. The card's address still works.
 * * **Wait until it answers.** A dev server prints its address before it
 *   serves it, and a pane that opens on a connection error reads as the
 *   product being broken. So this polls, and gives up quietly: the card is
 *   still there and the reply says what happened.
 */
import { isLocalAppAddress } from '@/lib/openInBrowser';
import { useBrowserStore } from '@/stores/browserStore';

/** The tools that start a server for the person to look at. */
export const APP_STARTERS: ReadonlySet<string> = new Set(['start_app', 'start_app_stack']);

/** How long to wait for a started server to answer before giving up. */
const WAIT_MS = 40_000;
const EVERY_MS = 500;

export interface StartedCall {
  server: string;
  tool: string;
  verdict: string;
  appUrl?: string;
}

interface Deps {
  /** Whether something answers at the address. Injected for tests. */
  answers?: (url: string) => Promise<boolean>;
  sleep?: (ms: number) => Promise<void>;
  waitMs?: number;
}

/** Any response at all counts, so the status does not matter: a 404 from a
 *  router with no `/` route is still a server that is up. `no-cors` because the
 *  body is never read, and a refused connection rejects either way. */
async function answersOverHttp(url: string): Promise<boolean> {
  try {
    await fetch(url, { mode: 'no-cors', cache: 'no-store', signal: AbortSignal.timeout(1500) });
    return true;
  } catch {
    return false;
  }
}

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** Addresses being waited on, so one start that is announced twice -- the
 *  step event and the call event -- opens the pane once. */
const waiting = new Set<string>();

/**
 * Returns true when the pane was opened. Never throws.
 */
export async function openStartedApp(call: StartedCall, deps: Deps = {}): Promise<boolean> {
  if (call.server !== 'code' || !APP_STARTERS.has(call.tool) || call.verdict !== 'allow') return false;
  return openWhenAnswering(call.appUrl, deps);
}

/**
 * The page of a stack, from the processes the backend reported. The same rule
 * as `packs/code/apps.py` `page_url`, and for the same reason: by the `role` a
 * process reports, never by its name alone, and nothing rather than a guess
 * when several answer and none says which is the page.
 */
export function frontendOf(
  processes: ReadonlyArray<{ url?: string | null; role?: string | null; running?: boolean }> | undefined,
): string {
  const live = (processes ?? []).filter((p) => p.running !== false && Boolean(p.url));
  const page = live.find((p) => p.role === 'frontend') ?? (live.length === 1 ? live[0] : undefined);
  if (page) return page.url ?? '';
  const unplaced = live.filter((p) => !p.role);
  return unplaced.length === 1 ? (unplaced[0].url ?? '') : '';
}

/** Open the pane at a local address once something answers there. Everything
 *  `openStartedApp` guards about the *address* lives here, so the Project
 *  page's own button, which knows the address already, cannot skip it. */
export async function openWhenAnswering(url: string | undefined, deps: Deps = {}): Promise<boolean> {
  if (!url || !isLocalAppAddress(url) || !window.zaram?.browser || waiting.has(url)) return false;
  const answers = deps.answers ?? answersOverHttp;
  const sleep = deps.sleep ?? wait;
  const limit = deps.waitMs ?? WAIT_MS;
  waiting.add(url);
  try {
    for (let waited = 0; waited <= limit; waited += EVERY_MS) {
      if (await answers(url)) {
        useBrowserStore.getState().show(url);
        return true;
      }
      await sleep(EVERY_MS);
    }
    return false;
  } catch {
    return false;
  } finally {
    waiting.delete(url);
  }
}
