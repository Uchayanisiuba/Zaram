/**
 * The mark is the second route home, and that is what this grades.
 *
 * `CLAUDE.md`: the return path must be visible and one click, and "never let
 * the animation be the only route back". The orb reverses the animation; this
 * is the route that sits in the same corner on every surface and names where it
 * goes. So the assertions are about behaviour and reachability, not appearance.
 *
 * The fallback case matters as much as the mark itself. Until the asset is
 * exported the button must still be a working way home — a logo that has not
 * shipped yet must not take the navigation with it.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';

import ZaramMark, { MARK_SRC } from './ZaramMark';

afterEach(cleanup);

describe('the mark', () => {
  it('is a button that goes home', () => {
    const onHome = vi.fn();
    render(<ZaramMark onHome={onHome} />);

    fireEvent.click(screen.getByRole('button', { name: /zaram/i }));

    expect(onHome).toHaveBeenCalledTimes(1);
  });

  it('names its destination rather than just showing a logo', () => {
    // A bare glyph with no accessible name is unreachable by keyboard or
    // screen reader, and the whole point of this control is that the way back
    // is *visible* — which has to include being announced.
    render(<ZaramMark onHome={() => {}} />);
    expect(
      screen.getByRole('button', { name: /back to the conversation/i }),
    ).toBeInTheDocument();
  });

  it('points at a local asset, never a remote one', () => {
    // `check-no-remote-assets.mjs` enforces this at build time for stylesheets
    // and fonts. A logo is the most likely thing to be hotlinked, and it would
    // be a request to a third party on every page load of a product whose
    // claim is that nothing leaves without permission.
    expect(MARK_SRC.startsWith('/')).toBe(true);
    expect(MARK_SRC).not.toMatch(/^https?:/);
  });

  it('still works as the way home when the asset is missing', () => {
    const onHome = vi.fn();
    render(<ZaramMark onHome={onHome} />);

    // jsdom never loads the image, so firing the error is what a missing file
    // does in a browser.
    fireEvent.error(screen.getByRole('presentation', { hidden: true }));

    const button = screen.getByRole('button', { name: /zaram/i });
    expect(button).toBeInTheDocument();
    fireEvent.click(button);
    expect(onHome).toHaveBeenCalledTimes(1);
    // The wordmark carries the identity in the meantime.
    expect(button.textContent).toContain('Zaram');
  });

  it('shows the icon alone, with no wordmark beside it', () => {
    // The surface name is already in the breadcrumb next to this. A wordmark
    // here would put the product name on screen twice in one corner.
    render(<ZaramMark onHome={() => {}} />);
    expect(screen.getByRole('button', { name: /zaram/i }).textContent).toBe('');
  });

  it('draws the bare mark on a tile it builds itself, not the baked icon', () => {
    // Decided 10 September 2026 (5eda403): the tile is CSS, made of the same
    // tokens as everything around it, so a theme change moves it. The asset
    // with the ground baked in — `zaram-icon.svg` — is what this must *not*
    // render, because a fixed bitmap of a colour decision is left behind by
    // every theme change. This test asserted the opposite for two days.
    render(<ZaramMark onHome={() => {}} />);
    expect(MARK_SRC).toContain('zaram-mark');
    expect(MARK_SRC).not.toContain('zaram-icon');
    const img = screen.getByRole('presentation', { hidden: true });
    expect(img.getAttribute('src')).toBe(MARK_SRC);
  });
});
