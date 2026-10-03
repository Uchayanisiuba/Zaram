/**
 * The slice of `window.zaram` the web code is allowed to assume.
 *
 * `electron/preload.js` exposes considerably more. This declares only what a
 * frontend module actually calls, on purpose: the bridge is the boundary
 * between a page and the machine, and a type that mirrors the whole of it
 * invites reaching for the rest.
 *
 * Optional throughout, because the same bundle runs in a browser during
 * development where `window.zaram` is undefined. A non-optional type here
 * would make every call site typecheck and then throw in the one place the
 * feature is easiest to develop.
 */
export {};

declare global {
  interface Window {
    zaram?: {
      isDesktop?: boolean;
      app?: {
        /** This launch's API credential, minted by the main process. */
        getApiSecret(): Promise<string>;
      };
      shell?: {
        /** Hand a URL to the user's real browser.
         *
         *  This read *"never opened in-app: a page rendered inside Zaram
         *  would run third-party script beside the Spine and its egress
         *  would be invisible to the gate"*, and **both halves have since
         *  been answered rather than waived — 3 October 2026.** The pane
         *  below is not beside the Spine: it is a separate `WebContents` on
         *  its own `persist:zaram-browser` partition, sandboxed, with no
         *  node and no preload, so it shares neither an origin nor a cookie
         *  jar with this renderer. And its egress is no longer invisible —
         *  `webRequest` reports every request, sub-resources included, to
         *  `POST /egress/browse`. That second objection was the real one,
         *  and closing it is most of what the pane cost.
         *
         *  This still exists and is still right for handing a link to the
         *  browser somebody already has open. It is no longer the only way
         *  to open a page. */
        openExternal(url: string): Promise<unknown>;
      };
      /** The browser pane. The view is main's; the chrome around it is this
       *  renderer's, which is what `setBounds` reconciles. */
      browser?: {
        open(): Promise<string | null>;
        select(id: string): Promise<void>;
        /** Resolves to the policy's decision. A refusal is an answer the
         *  address bar renders — `browse-not-allowed` is a different thing
         *  to say than `not-an-address`, and a boolean could say neither. */
        navigate(id: string, url: string): Promise<BrowserDecision | null>;
        close(id: string): Promise<void>;
        setBounds(bounds: { x: number; y: number; width: number; height: number }): Promise<void>;
        act(id: string, what: 'back' | 'forward' | 'reload' | 'stop'): Promise<void>;
        show(): Promise<void>;
        hide(): Promise<void>;
        state(): Promise<{ tabs: BrowserTab[]; activeId: string | null }>;
        onTabs(listener: (payload: BrowserTabsEvent) => void): () => void;
      };
      /** The ambient overlay — see `electron/native/ambient.js`. Every member
       *  reports something the user just did; none of them observes. */
      ambient?: {
        dismiss(): Promise<{ dismissed: boolean }>;
        hover(hovered: boolean): Promise<{ hovered: boolean }>;
        summon(): Promise<{ summoned: boolean }>;
      };
    };
  }
}

/** One tab in the browser pane, as main reports it. */
export interface BrowserTab {
  id: string;
  url: string;
  title: string;
  active: boolean;
  canGoBack?: boolean;
  canGoForward?: boolean;
  loading?: boolean;
}

/** What main pushes when a tab navigates, loads, or is refused. */
export interface BrowserTabsEvent {
  tabs?: BrowserTab[];
  activeId?: string | null;
  /** A navigation the policy stopped — a link click never passes through
   *  `navigate`, so this is the only way the renderer hears about one. */
  refused?: { tabId: string; url: string };
}

/** The policy's answer to "may this be opened", from `browserPolicy.js`. */
export interface BrowserDecision {
  ok: boolean;
  allow: boolean;
  url?: string;
  host?: string;
  scope?: 'local' | 'web';
  /** `empty`, `not-an-address`, `scheme`, `browse-not-allowed`, `no-such-tab`. */
  reason?: string;
  typed?: string;
}
