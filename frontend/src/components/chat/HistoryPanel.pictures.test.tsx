/**
 * @vitest-environment jsdom
 *
 * Shortening how long the pictures a conversation kept are held.
 *
 * Pictures are copied beside a conversation so its pages keep showing them
 * (`backend/conversations/pictures.py`). They stay as long as the conversation
 * does, and this is the control that lets a person end that sooner without
 * losing the conversation -- the retention answer the store owes. Its own file,
 * for the reason `HistoryPanel.finding.test.tsx` gives: `HistoryPanel.test.tsx`
 * mocks the client down to two functions on purpose.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// The first render pays for the panel's icons and stores (~3 s measured on an
// idle machine), which is over the default budget when the machine is busy.
vi.setConfig({ testTimeout: 20000 });

const fetchConversations = vi.fn();
const removeConversationPictures = vi.fn();
const deleteConversation = vi.fn(async () => ({ note: '' }));

vi.mock('@/services/conversationsClient', () => ({
  fetchConversations: (...a: unknown[]) => fetchConversations(...(a as [])),
  searchConversations: vi.fn(async () => []),
  pinConversation: vi.fn(),
  deleteConversation: (...a: unknown[]) => deleteConversation(...(a as [])),
  removeConversationPictures: (...a: unknown[]) => removeConversationPictures(...(a as [])),
}));

import HistoryPanel from './HistoryPanel';
import { usePictureStore } from '@/stores/pictureStore';

const row = (over: Record<string, unknown> = {}) => ({
  id: 'conv_1',
  title: 'a site from my photo',
  projectId: '',
  createdAt: 1,
  updatedAt: 1,
  messageCount: 2,
  pinned: false,
  ...over,
});

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  fetchConversations.mockReset().mockResolvedValue([row()]);
  removeConversationPictures.mockReset().mockResolvedValue({ removed: 2, bytes: 1234 });
  usePictureStore.setState({ held: { att_1: 'data:image/png;base64,AAAA' } });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const user = () => userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

async function open() {
  render(<HistoryPanel />);
  await user().click(screen.getByRole('button', { name: /past conversations/i }));
  await act(async () => {
    vi.advanceTimersByTime(400);
  });
}

describe('removing the pictures kept with a conversation', () => {
  it('asks the backend for that conversation and says how many went', async () => {
    await open();

    await user().click(screen.getByTestId('remove-pictures-conv_1'));

    expect(removeConversationPictures).toHaveBeenCalledWith('conv_1');
    expect(await screen.findByText(/Removed 2 pictures kept with that conversation/)).toBeTruthy();
    expect(deleteConversation).not.toHaveBeenCalled();
  });

  it('keeps the conversation in the list', async () => {
    await open();

    await user().click(screen.getByTestId('remove-pictures-conv_1'));

    expect(screen.getByText('a site from my photo')).toBeTruthy();
  });

  it('says so when there was nothing to remove', async () => {
    removeConversationPictures.mockResolvedValue({ removed: 0, bytes: 0 });
    await open();

    await user().click(screen.getByTestId('remove-pictures-conv_1'));

    expect(await screen.findByText('No pictures were kept with that conversation.')).toBeTruthy();
  });

  it('says so when it failed rather than failing quietly', async () => {
    removeConversationPictures.mockRejectedValue(new Error('The backend did not answer.'));
    await open();

    await user().click(screen.getByTestId('remove-pictures-conv_1'));

    expect(await screen.findByText('The backend did not answer.')).toBeTruthy();
  });
});
