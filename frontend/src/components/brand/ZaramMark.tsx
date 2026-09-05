/**
 * The Zaram mark, and the way home.
 *
 * **It is a button, not decoration.** `CLAUDE.md` requires that the route back
 * from a workspace to the conversation is visible and one click, and warns
 * "never let the animation be the only route back". The orb reverses the
 * animation and this is the second route — the one that names its destination
 * and is in the same place on every surface.
 *
 * **Home is the landing, not the conversation.** Clicking this closes the chat
 * and returns to the landing with the orb at rest; it does not open a
 * conversation. That keeps two gestures distinct instead of redundant: the orb
 * is the way *into* the conversation, the mark is the way *back to the start*.
 * A logo that opened chat would make the orb's one job ambiguous.
 *
 * **It is absent on the landing**, because `TopNav` is. The landing is already
 * the brand moment — the orb is the largest thing on screen — and a second mark
 * in the corner would compete with it for the same meaning.
 *
 * ## The asset
 *
 * `public/brand/zaram-mark.svg`, which does not exist yet. Until it does this
 * renders the wordmark that was already there, so nothing is broken and nothing
 * is a placeholder pretending to be a logo. The instant the file appears the
 * mark takes over — see `public/brand/README.md` for what to export.
 *
 * The asset must be local. `frontend/scripts/check-no-remote-assets.mjs` fails
 * the build on anything fetched from a CDN, and a logo is exactly the kind of
 * thing somebody would be tempted to hotlink.
 */
import { useState } from 'react';

/**
 * The app icon — the mark on its rounded ground, as on the brand sheet.
 *
 * The tile rather than the bare glyph, because this corner is the same object
 * the user clicked on their desktop and sees in the taskbar. Making it a
 * different silhouette in the third place they meet it is how a mark stops
 * being recognised.
 *
 * SVG rather than the 512px PNG: it renders at 32px here, and a downscaled
 * raster at that size loses the diagonal gap that gives the mark its character.
 */
export const MARK_SRC = '/brand/zaram-icon.svg';

/** The tile is square. The bare glyph is 1.3073:1 — see zaram-mark.svg. */
export const MARK_ASPECT = 1;

interface ZaramMarkProps {
  /** Go home: the landing, with the conversation closed. */
  onHome: () => void;
  /** Icon **height** in px. Width follows the asset's aspect ratio. */
  size?: number;
  /**
   * Show the "Zaram" wordmark beside the icon. Off by default: the icon is the
   * identity, the surface name is already in the breadcrumb next to it, and a
   * wordmark there would have the product name on screen twice.
   */
  withWordmark?: boolean;
}

export default function ZaramMark({ onHome, size = 51, withWordmark = false }: ZaramMarkProps) {
  // `onError` rather than a build-time check: whether the file is present is a
  // fact about the deployed bundle, and a missing logo must degrade to the
  // wordmark rather than to a broken-image icon.
  const [markFailed, setMarkFailed] = useState(false);

  return (
    <button
      type="button"
      onClick={onHome}
      aria-label="Zaram — back to the conversation"
      title="Back to the conversation"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        background: 'none',
        border: 'none',
        padding: 0,
        cursor: 'pointer',
        // The mark is the one fixed point in the chrome; it should not shift
        // when the surface beside it changes width.
        flexShrink: 0,
      }}
    >
      {!markFailed && (
        <img
          src={MARK_SRC}
          alt=""
          aria-hidden="true"
          width={Math.round(size * MARK_ASPECT)}
          height={size}
          onError={() => setMarkFailed(true)}
          style={{
            display: 'block',
            height: size,
            width: Math.round(size * MARK_ASPECT),
          }}
        />
      )}
      {/* The wordmark is also the fallback: with no icon the button still has
          to be a visible, named way home rather than an empty target. */}
      {(withWordmark || markFailed) && (
        <span
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 'var(--text-h1)',
            fontWeight: 600,
            letterSpacing: '0.02em',
          }}
          className="text-gradient-orb"
        >
          Zaram
        </span>
      )}
    </button>
  );
}
