/**
 * @vitest-environment jsdom
 *
 * What a tool showed Zaram, on the card under the reply.
 *
 * 10 October 2026: the desktop driver returns a screenshot with every window it
 * reads. It is kept in Zaram's own picture folder, which belongs to no project, so
 * the card must fetch it from there — with the credential, like every request —
 * and need no project open. The code pack's `look_at_app` keeps its pictures
 * under the project, as before.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

import AppCard from './AppCard';
import { useChatStore, type ChatToolCall } from '@/stores/chatStore';

const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => new Response(new Blob(['png'], { type: 'image/png' })));

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: () => 'blob:shot', revokeObjectURL: () => undefined }));
  fetchMock.mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const shot = (server: string, image: string): ChatToolCall => ({
  server,
  tool: server === 'code' ? 'look_at_app' : 'get_window_state',
  verdict: 'allow',
  reason: '',
  target: 'Google',
  image,
});

describe('the picture a tool returned', () => {
  it('comes from Zaram\u2019s own folder, with no project open', async () => {
    useChatStore.setState({ projectId: '' });
    render(<AppCard call={shot('cua-driver', 'C:\\data\\screens\\tools\\20261010-1.png')} />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/tools\/pictures\/20261010-1\.png$/);
    expect(await screen.findByTestId('app-screenshot')).toHaveAttribute('alt', 'What the tool showed Zaram');
  });

  it('a project page still comes from the project', async () => {
    useChatStore.setState({ projectId: 'ride-share' });
    render(<AppCard call={shot('code', 'page.png')} />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/projects\/ride-share\/screens\/page\.png$/);
  });
});
