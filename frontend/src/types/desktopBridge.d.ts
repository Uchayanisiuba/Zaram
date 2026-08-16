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
