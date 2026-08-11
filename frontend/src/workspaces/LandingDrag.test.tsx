/**
 * The orbit node still opens when you click it.
 *
 * Narrow on purpose, and the omission is the interesting part.
 *
 * Dragging a node must **not** navigate: a drag ends with a pointerup over the
 * node, the browser reports that as a click, and the naive version of this
 * feature therefore opens Memory when you move Memory out of the way. That is
 * the failure the guard in `Landing.tsx` exists to prevent, and **it is not
 * tested here, because jsdom cannot drive it.** framer-motion's drag needs real
 * layout to decide that the pointer has passed the drag threshold, and jsdom
 * reports every element as zero-sized, so `onDragStart` never fires and the
 * guard never arms. A test written against that would pass whether or not the
 * guard existed — a test asserting nothing, which is worse than no test.
 *
 * It was verified in a browser instead, on 11 August 2026: pressing Memory and
 * moving 168px left and 120px down carried the node with the pointer
 * (`matrix(1.06, 0, 0, 1.06, -168, 120)`), releasing returned the drag layer to
 * `transform: none`, and the shell stayed on the landing. A plain click
 * afterwards navigated to Memory.
 *
 * What remains here is the half jsdom can honestly answer, and it is not
 * nothing: **a guard that is too eager eats the click it was built beside.** A
 * menu you cannot open is a worse bug than one that opens by accident, and that
 * regression is one line away at all times.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';
import Landing from './Landing';

afterEach(cleanup);

describe('an orbit node', () => {
  it('navigates when it is clicked', async () => {
    const onNavigate = vi.fn();
    render(<Landing onNavigate={onNavigate} onOrbTap={() => {}} />);

    fireEvent.click(screen.getByRole('button', { name: /Memory/ }));

    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith('memory'));
  });

  it('navigates to the node that was clicked, not a fixed one', async () => {
    // The drag layer sits between the node and its handler. Wiring it wrong
    // once produced a shared closure; this is cheap insurance against that.
    const onNavigate = vi.fn();
    render(<Landing onNavigate={onNavigate} onOrbTap={() => {}} />);

    fireEvent.click(screen.getByRole('button', { name: /Knowledge/ }));

    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith('knowledge'));
  });
});
