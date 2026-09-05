/**
 * The composer's account of what is in scope for the next message.
 *
 * Three things are being graded, and the first two are rules rather than
 * presentation.
 *
 * **Keep is an offer, not a gate** (rule 7d). A file is usable the moment it is
 * attached; adding it to Knowledge is a separate decision made afterwards. A
 * chip that demanded the decision up front would make every question about a
 * document a commitment to remember it for ever.
 *
 * **A refusal is a row, not a toast.** The user is about to ask a question
 * whose answer depends on what is actually attached, so "Zaram has no parser
 * for .zip" cannot disappear on a timer. (Images used to be the example here
 * and are no longer refused — they attach, and whether a model can *see* one
 * is decided in `/chat` by the capability gate.)
 *
 * **The size is shown before the question is asked**, because it is what
 * decides whether the reply says "read in full" or "searched it and used 3
 * sections" — and a consequence explained only afterwards reads as a surprise.
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import AttachmentChips from './AttachmentChips';
import type { ChatAttachment } from '@/services/attachmentsClient';

const file = (over: Partial<ChatAttachment> = {}): ChatAttachment => ({
  id: 'att_1',
  name: 'agreement.pdf',
  suffix: '.pdf',
  chars: 14_000,
  pages: 12,
  parser: 'pypdf',
  kind: 'document',
  created_at: 0,
  ...over,
});

const noop = () => undefined;

function renderChips(over: Partial<React.ComponentProps<typeof AttachmentChips>> = {}) {
  const props = {
    attachments: [file()],
    refused: [],
    kept: [],
    busy: null,
    onDetach: noop,
    onKeep: noop,
    onDismissRefusal: noop,
    ...over,
  };
  return { ...render(<AttachmentChips {...props} />), props };
}

describe('what is attached', () => {
  it('names the file', () => {
    renderChips();
    expect(screen.getByText('agreement.pdf')).toBeTruthy();
  });

  it('shows its length in pages, before the question is asked', () => {
    renderChips();
    // Pages rather than bytes: a byte count describes the file, and what
    // matters is how much of it can be read at once.
    expect(screen.getByText('12 pages')).toBeTruthy();
  });

  it('falls back to characters where the format has no pages', () => {
    renderChips({ attachments: [file({ pages: 0, chars: 8200 })] });
    expect(screen.getByText('8k characters')).toBeTruthy();
  });

  it('says image rather than counting characters it does not have', () => {
    renderChips({
      attachments: [
        file({ name: 'receipt.png', suffix: '.png', kind: 'image', chars: 0, pages: 0 }),
      ],
    });

    // "0 characters" would read as a file that failed to parse rather than one
    // with nothing to parse, which is the opposite of what happened.
    expect(screen.getByText('image')).toBeTruthy();
    expect(screen.queryByText('0 characters')).toBeNull();
  });

  it('renders nothing at all when there is nothing attached', () => {
    const { container } = renderChips({ attachments: [], refused: [] });
    // An empty container above the composer is clutter that says nothing.
    expect(container.firstChild).toBeNull();
  });
});

describe('keeping is an offer', () => {
  it('offers Keep on a file that is only attached', () => {
    renderChips();
    expect(screen.getByRole('button', { name: 'Keep' })).toBeTruthy();
  });

  it('does not offer it again once the file is in Knowledge', () => {
    renderChips({ kept: ['att_1'] });

    // Offering again would either duplicate the source or silently do
    // nothing, and both teach the user not to trust the button.
    expect(screen.queryByRole('button', { name: 'Keep' })).toBeNull();
    expect(screen.getByText('In Knowledge')).toBeTruthy();
  });

  it('asks the caller to keep the file the user pointed at', () => {
    const onKeep = vi.fn();
    renderChips({
      attachments: [file(), file({ id: 'att_2', name: 'brief.txt' })],
      onKeep,
    });

    fireEvent.click(screen.getAllByRole('button', { name: 'Keep' })[1]);

    expect(onKeep).toHaveBeenCalledWith('att_2');
  });

  it('cannot be pressed twice while the first press is in flight', () => {
    renderChips({ busy: 'att_1' });
    // Two presses would ingest the same document twice, and the second source
    // is indistinguishable from a real duplicate afterwards.
    const keep = screen.queryByRole('button', { name: 'Keep' });
    expect(keep).toBeNull();
  });
});

describe('detaching', () => {
  it('removes the file the user pointed at', () => {
    const onDetach = vi.fn();
    // Two files, because with one the id under test is also `attachments[0]`
    // and the assertion holds however the component picks it. The first
    // version of this test had one file and survived the component being
    // changed to always detach the first.
    renderChips({
      attachments: [file(), file({ id: 'att_2', name: 'brief.txt' })],
      onDetach,
    });

    fireEvent.click(screen.getByRole('button', { name: 'Remove brief.txt' }));

    expect(onDetach).toHaveBeenCalledWith('att_2');
  });
});

describe('a file that was refused', () => {
  const refusal = {
    name: 'archive.zip',
    reason:
      'Zaram has no parser for .zip. It can read: .csv, .docx, .json, .markdown, .md, .pdf, .rst, .txt, .xlsx, .yaml, .yml.',
  };

  it('shows the backend sentence verbatim', () => {
    renderChips({ attachments: [], refused: [refusal] });

    // The backend knows *why* — that this is an image, or which formats can be
    // read. Rewriting it here produces a second, vaguer copy that drifts.
    expect(screen.getByText(refusal.reason)).toBeTruthy();
  });

  it('is shown beside the files that did attach, not instead of them', () => {
    renderChips({ refused: [refusal] });

    // Dropping four files of which one is a screenshot attaches three. A
    // failure that hid the successes would be a worse report than either.
    expect(screen.getByText('agreement.pdf')).toBeTruthy();
    expect(screen.getByText(refusal.reason)).toBeTruthy();
  });

  it('can be dismissed once read', () => {
    const onDismissRefusal = vi.fn();
    renderChips({ attachments: [], refused: [refusal], onDismissRefusal });

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss archive.zip' }));

    expect(onDismissRefusal).toHaveBeenCalledWith('archive.zip');
  });
});
