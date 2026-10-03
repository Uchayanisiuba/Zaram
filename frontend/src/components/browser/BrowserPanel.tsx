/**
 * The browser pane: tabs, an address bar, and a hole for the page.
 *
 * Asked for 3 October 2026 — *"all pages are for the user and Zaram to use
 * and drive, I want it to feel like what Claude has"* — alongside being able
 * to reach localhost and interact with apps being built in Zaram.
 *
 * **This component never renders a page.** The page is a `BrowserView` in
 * the main process, painted *above* this window, and the only thing this
 * file does about it is measure the rectangle it should occupy and send
 * that over IPC. Everything visible here is the chrome around the hole.
 *
 * Three consequences, all of them things that look like bugs if forgotten:
 *
 * * The view covers whatever is underneath it, so leaving the pane must
 *   `hide()` rather than merely unmount — an unmounted React tree leaves a
 *   `BrowserView` sitting over Memory.
 * * The content area needs a measured rectangle on every resize, so a
 *   `ResizeObserver` drives `setBounds` rather than a layout effect alone.
 * * The new-tab page *is* React, so the view has to be hidden while it is
 *   showing or it would cover it.
 *
 * Without a desktop host — a browser tab during development — there is no
 * bridge and no view. The pane says so rather than rendering chrome around
 * a hole that will never be filled.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  ArrowRight,
  Plus,
  RotateCw,
  X,
} from 'lucide-react';

import NewTabPage from './NewTabPage';

type Tab = NonNullable<Window['zaram']> extends { browser?: infer B }
  ? B extends { state(): Promise<{ tabs: infer T }> }
    ? T extends (infer One)[]
      ? One
      : never
    : never
  : never;

/** What the address bar says after a refusal.
 *
 *  Each reason is a different thing to tell somebody, which is why the
 *  bridge returns the policy's whole decision rather than a boolean.
 *  "Browsing is off" has a fix; "that is not an address" has a different
 *  one; and a refused scheme is neither. */
function refusalText(reason: string | undefined, typed: string): string {
  switch (reason) {
    case 'browse-not-allowed':
      return 'Browsing the web is off. Turn it on in Settings → Privacy to open pages that are not on this machine.';
    case 'not-an-address':
      return `“${typed}” is not an address. Zaram will not quietly search for it — that would contact a site you did not name.`;
    case 'scheme':
      return 'Only http and https pages open here.';
    case 'empty':
      return '';
    default:
      return 'That page could not be opened.';
  }
}

interface Props {
  /** Where to go on open, if the pane was summoned at an address. Read once
   *  by the caller's store; this component never writes it back. */
  initialUrl?: string | null;
  onClose?: () => void;
}

export default function BrowserPanel({ initialUrl, onClose }: Props = {}) {
  const bridge = typeof window !== 'undefined' ? window.zaram?.browser : undefined;
  const holeRef = useRef<HTMLDivElement | null>(null);
  const [tabs, setTabs] = useState<Tab[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [typed, setTyped] = useState('');
  const [refusal, setRefusal] = useState('');

  const active = tabs.find((t) => (t as { id: string }).id === activeId) as
    | { id: string; url: string; title: string; canGoBack?: boolean; canGoForward?: boolean; loading?: boolean }
    | undefined;
  // A tab with no URL is showing the new-tab page, which is React and would
  // be covered by the view.
  const showingNewTab = !active?.url;

  /** Tell main where the page goes. */
  const sendBounds = useCallback(() => {
    const node = holeRef.current;
    if (!node || !bridge) return;
    const box = node.getBoundingClientRect();
    bridge.setBounds({ x: box.left, y: box.top, width: box.width, height: box.height });
  }, [bridge]);

  // Open one tab on first mount, and take the view away on the way out.
  useEffect(() => {
    if (!bridge) return undefined;
    let live = true;
    bridge.state().then((state) => {
      if (!live) return;
      if (!state.tabs.length) bridge.open();
      else {
        setTabs(state.tabs as Tab[]);
        setActiveId(state.activeId);
        bridge.show();
      }
    });
    return () => {
      live = false;
      // **Hide, never close.** The tabs outlive this panel: somebody who
      // steps into Memory and comes back expects what they had open. What
      // must not outlive it is the view sitting over the surface they left
      // for.
      bridge.hide();
    };
  }, [bridge]);

  // Main pushes tab state; it is never polled. A page's title arrives when
  // it arrives, and a strip that lagged by a poll interval reads as the
  // browser being slow.
  useEffect(() => {
    if (!bridge) return undefined;
    return bridge.onTabs((payload) => {
      if (payload.tabs) setTabs(payload.tabs as Tab[]);
      if (payload.activeId !== undefined) setActiveId(payload.activeId);
      if (payload.refused) {
        // A link click never passes through `navigate`, so this push is the
        // only way the renderer hears that one was stopped.
        setRefusal(refusalText('browse-not-allowed', payload.refused.url));
      }
    });
  }, [bridge]);

  // The address bar follows the page, except while it is being typed into.
  useEffect(() => {
    setTyped(active?.url ?? '');
    setRefusal('');
  }, [active?.url, activeId]);

  // Keep the hole and the view in step through every resize, not only the
  // ones React re-renders for.
  useEffect(() => {
    if (!bridge) return undefined;
    sendBounds();
    const observer = new ResizeObserver(sendBounds);
    if (holeRef.current) observer.observe(holeRef.current);
    window.addEventListener('resize', sendBounds);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', sendBounds);
    };
  }, [bridge, sendBounds]);

  // The view would cover the new-tab page, which is React.
  useEffect(() => {
    if (!bridge) return;
    if (showingNewTab) bridge.hide();
    else {
      bridge.show();
      sendBounds();
    }
  }, [bridge, showingNewTab, sendBounds]);

  const go = useCallback(
    async (url: string) => {
      if (!bridge || !activeId) return;
      const decision = await bridge.navigate(activeId, url);
      setRefusal(decision && !decision.allow ? refusalText(decision.reason, url) : '');
    },
    [bridge, activeId],
  );

  // The address the pane was summoned at, once a tab exists to put it in.
  // Guarded so that reopening the pane does not re-navigate a tab the
  // person has since taken somewhere else.
  const sent = useRef<string | null>(null);
  useEffect(() => {
    if (!initialUrl || !activeId || sent.current === initialUrl) return;
    sent.current = initialUrl;
    go(initialUrl);
  }, [initialUrl, activeId, go]);

  if (!bridge) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-center text-sm text-slate-500">
        The browser pane needs the desktop app. In a browser tab there is no
        window to put it over.
      </div>
    );
  }

  // **Portalled and fixed, like every other panel that comes forward.**
  // `CodePreviewPanel`'s note gives the reason — *"one way to bring
  // something forward is a thing users learn once"* — and there is a second
  // reason here that is not a matter of taste: the hole is measured with
  // `getBoundingClientRect`, which is in window coordinates, and that is
  // the frame the `BrowserView` is positioned in. An inline panel inside a
  // scrolling conversation would hand main a rectangle that drifts the
  // moment anything scrolls.
  //
  // No backdrop click-to-close: the page is above this element, so a click
  // on it never reaches here, and a dismissal that works everywhere except
  // over the content is worse than none.
  return createPortal(
    <motion.div
      className="fixed inset-0 z-[90] flex flex-col bg-slate-950"
      data-testid="browser-panel"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      role="dialog"
      aria-label="Browser"
    >
      {/* Tabs */}
      <div className="flex items-end gap-1 border-b border-slate-800 px-2 pt-2">
        {tabs.map((raw) => {
          const tab = raw as { id: string; title: string; url: string };
          const isActive = tab.id === activeId;
          return (
            <div
              key={tab.id}
              className={`group flex max-w-[180px] items-center gap-2 rounded-t-md px-3 py-1.5 text-xs ${
                isActive ? 'bg-slate-900 text-slate-100' : 'text-slate-500 hover:bg-slate-900/50'
              }`}
            >
              <button
                type="button"
                data-testid={`tab-${tab.id}`}
                onClick={() => bridge.select(tab.id)}
                className="min-w-0 flex-1 truncate text-left"
                title={tab.url || tab.title}
              >
                {tab.title || 'New tab'}
              </button>
              <button
                type="button"
                aria-label="Close tab"
                data-testid={`close-${tab.id}`}
                onClick={() => bridge.close(tab.id)}
                className="shrink-0 opacity-0 transition group-hover:opacity-100"
              >
                <X size={12} />
              </button>
            </div>
          );
        })}
        <button
          type="button"
          aria-label="New tab"
          data-testid="new-tab"
          onClick={() => bridge.open()}
          className="mb-1 rounded p-1 text-slate-500 transition hover:bg-slate-900 hover:text-slate-200"
        >
          <Plus size={14} />
        </button>
      </div>

      {/* Address bar */}
      <div className="flex items-center gap-2 border-b border-slate-800 px-3 py-2">
        <button
          type="button"
          aria-label="Back"
          disabled={!active?.canGoBack}
          onClick={() => activeId && bridge.act(activeId, 'back')}
          className="rounded p-1 text-slate-400 transition hover:bg-slate-900 disabled:opacity-30"
        >
          <ArrowLeft size={15} />
        </button>
        <button
          type="button"
          aria-label="Forward"
          disabled={!active?.canGoForward}
          onClick={() => activeId && bridge.act(activeId, 'forward')}
          className="rounded p-1 text-slate-400 transition hover:bg-slate-900 disabled:opacity-30"
        >
          <ArrowRight size={15} />
        </button>
        <button
          type="button"
          aria-label="Reload"
          onClick={() => activeId && bridge.act(activeId, 'reload')}
          className="rounded p-1 text-slate-400 transition hover:bg-slate-900"
        >
          <RotateCw size={14} className={active?.loading ? 'animate-spin' : undefined} />
        </button>
        <form
          className="flex-1"
          onSubmit={(event) => {
            event.preventDefault();
            go(typed);
          }}
        >
          <input
            data-testid="address-bar"
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            placeholder="Type a URL"
            spellCheck={false}
            className="w-full rounded-md border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-200 outline-none focus:border-indigo-500"
          />
        </form>
        {onClose && (
          <button
            type="button"
            aria-label="Close the browser"
            data-testid="close-browser"
            onClick={onClose}
            className="rounded p-1 text-slate-400 transition hover:bg-slate-900"
          >
            <X size={15} />
          </button>
        )}
      </div>

      {refusal && (
        <p
          data-testid="browser-refusal"
          className="border-b border-amber-900/40 bg-amber-950/30 px-4 py-2 text-xs text-amber-200"
        >
          {refusal}
        </p>
      )}

      {/* The hole. Either the new-tab page, or the rectangle the view fills. */}
      <div ref={holeRef} className="relative min-h-0 flex-1">
        {showingNewTab && <NewTabPage onOpen={go} />}
      </div>
    </motion.div>,
    document.body,
  );
}
