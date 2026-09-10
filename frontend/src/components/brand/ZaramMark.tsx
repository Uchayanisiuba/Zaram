/**
 * The Zaram mark on its tile, and the way home.
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
 * **It was absent on the landing, and is not any more — corrected 10 September
 * 2026.** The reasoning was that the landing is already the brand moment, so a
 * second mark would compete. A mark was added there later anyway and the two
 * never met: the landing drew a bare glyph in a tile it built itself while this
 * rendered `zaram-icon.svg`, which has the ground baked into the asset. Two
 * silhouettes for one identity.
 *
 * ## The tile is CSS, not the asset — decided 10 September 2026
 *
 * Both existed and the maintainer chose this one. It is the better call for a
 * reason worth writing down: **the asset's ground is a fixed bitmap of a colour
 * decision, and this one is made of the same tokens as everything around it.**
 * A theme change moves this tile and leaves `zaram-icon.svg` behind — the same
 * argument the syntax-highlighting theme makes against importing highlight.js's
 * own stylesheet.
 *
 * So the glyph is `zaram-mark.svg`, 130.73:100, drawn on a ground built here.
 *
 * **Indigo, and that is not an aesthetic choice.** `docs/UI-SPEC.md` assigns
 * violet to **cloud**, so a violet tile would put "your data left the device"
 * in the corner of every surface, permanently and falsely. `CLAUDE.md`'s 15
 * August face-colour argument lands on indigo for the same reason: it is the
 * implementation's own accent and it is nobody's state.
 *
 * The gradient runs from the accent to nothing rather than between two colours.
 * Two stops of equal weight make a badge; one fading out makes a surface
 * catching light.
 *
 * The asset must be local. `frontend/scripts/check-no-remote-assets.mjs` fails
 * the build on anything fetched from a CDN, and a logo is exactly the kind of
 * thing somebody would be tempted to hotlink.
 */
import { useState } from 'react';
import type { CSSProperties } from 'react';

/** The bare glyph. The ground it sits on is drawn below, in tokens. */
export const MARK_SRC = '/brand/zaram-mark.svg';

/** Width ÷ height of the glyph, read off its `viewBox`: `0 0 130.73 100`. */
export const MARK_ASPECT = 1.3073;

/** How much of the tile the glyph occupies across. The rest is the ground. */
const GLYPH_FRACTION = 0.62;

const TILE_STYLE: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  borderRadius: 16,
  background: 'linear-gradient(145deg, rgba(99,102,241,0.20), rgba(255,255,255,0.03))',
  border: '1px solid rgba(99,102,241,0.28)',
  backdropFilter: 'blur(10px)',
  boxShadow: '0 4px 24px rgba(0,0,0,0.3)',
  flexShrink: 0,
};

interface ZaramMarkProps {
  /** Go home: the landing, with the conversation closed. */
  onHome: () => void;
  /** The tile's edge in px. The glyph is a fraction of it. */
  size?: number;
  /**
   * Show the "Zaram" wordmark beside the tile. Off by default: the icon is the
   * identity, the surface name is already in the breadcrumb next to it, and a
   * wordmark there would have the product name on screen twice.
   */
  withWordmark?: boolean;
  /**
   * Whether it is a control at all. Default true.
   *
   * The landing passes `false` while the conversation is closed, because
   * `onHome` returns to the landing at rest and that is already where you are.
   * A button there would be a control that does nothing — the defect this
   * codebase keeps paying for, most recently in a history lip that could open
   * a panel and never close it. Identical tile and glyph either way, so nothing
   * moves when it becomes live.
   */
  interactive?: boolean;
}

export default function ZaramMark({
  onHome,
  size = 51,
  withWordmark = false,
  interactive = true,
}: ZaramMarkProps) {
  // `onError` rather than a build-time check: whether the file is present is a
  // fact about the deployed bundle, and a missing glyph must degrade to the
  // wordmark rather than to a broken-image icon.
  const [markFailed, setMarkFailed] = useState(false);

  const glyphWidth = Math.round(size * GLYPH_FRACTION);
  const glyphHeight = Math.round(glyphWidth / MARK_ASPECT);

  const inner = (
    <>
      {!markFailed && (
        <span style={{ ...TILE_STYLE, width: size, height: size }}>
          <img
            src={MARK_SRC}
            alt=""
            aria-hidden="true"
            width={glyphWidth}
            height={glyphHeight}
            onError={() => setMarkFailed(true)}
            style={{ display: 'block', width: glyphWidth, height: glyphHeight }}
          />
        </span>
      )}
      {/* The wordmark is also the fallback: with no glyph the control still has
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
    </>
  );

  const layout: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    background: 'none',
    border: 'none',
    padding: 0,
    // The mark is the one fixed point in the chrome; it should not shift when
    // the surface beside it changes width.
    flexShrink: 0,
  };

  if (!interactive) {
    return (
      <div aria-hidden style={layout}>
        {inner}
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onHome}
      aria-label="Zaram — back to the conversation"
      title="Back to the conversation"
      style={{ ...layout, cursor: 'pointer' }}
    >
      {inner}
    </button>
  );
}
