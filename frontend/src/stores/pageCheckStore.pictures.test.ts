/**
 * @vitest-environment jsdom
 *
 * The page is checked with the person's pictures in it, and the line under the
 * reply says when one could not be given.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

const checkPage = vi.fn();
const buildFrameDoc = vi.fn(async (_block: unknown) => '<doc/>');
const JPEG = 'data:image/jpeg;base64,/9j/4AAQ';

let held: Record<string, string | null> = {};
const chat = {
  isStreaming: false,
  sessionId: 'session-1',
  messages: [] as { role: string; text: string; attachments?: unknown[] }[],
};
vi.mock('@/stores/chatStore', () => ({ useChatStore: { getState: () => ({ send: vi.fn(), ...chat }) } }));
vi.mock('@/stores/pictureStore', () => ({
  usePictureStore: { getState: () => ({ held, ensure: vi.fn(async () => {}) }) },
}));
vi.mock('@/services/pageCheckClient', () => ({ checkPage: (...a: unknown[]) => checkPage(...a) }));
vi.mock('@/lib/previewFrame', () => ({ buildFrameDoc: (b: unknown) => buildFrameDoc(b) }));

const clean = { checked: true, ok: true, hung: false, errors: [], blocked: [], blockedSeconds: 0, problems: [], note: '' };
const reply = '```html\n<html><body><img src="photo-1.jpg"><script>var a = 1;</script></body></html>\n```';

beforeEach(() => {
  vi.resetModules();
  window.localStorage.clear();
  checkPage.mockReset().mockResolvedValue(clean);
  buildFrameDoc.mockClear();
  chat.messages = [
    {
      role: 'user',
      text: 'a site from this photo',
      attachments: [{ id: 'a1', kind: 'image', name: 'me.jpg', pageName: 'photo-1.jpg' }],
    },
    { role: 'assistant', text: reply },
  ];
});

describe('a page that uses an attached picture', () => {
  it('is checked with the picture in, and the line has nothing to add', async () => {
    held = { a1: JPEG };
    const { usePageCheckStore, replyKey } = await import('./pageCheckStore');
    await usePageCheckStore.getState().check(reply, 'a site');
    const sent = buildFrameDoc.mock.calls[0][0] as { pictures: Record<string, string | null>; code: string };
    expect(sent.pictures).toEqual({ 'photo-1.jpg': JPEG });
    // The page keeps its names; the frame builder puts the bytes in.
    expect(sent.code).toContain('photo-1.jpg');
    expect(usePageCheckStore.getState().byReply[replyKey(reply)].pictures).toBeUndefined();
  });

  it('says when the picture is no longer attached', async () => {
    held = { a1: null };
    const { usePageCheckStore, replyKey } = await import('./pageCheckStore');
    await usePageCheckStore.getState().check(reply, 'a site');
    const state = usePageCheckStore.getState().byReply[replyKey(reply)];
    expect(state.status).toBe('clean');
    expect(state.pictures?.join(' ')).toContain('photo-1.jpg is no longer attached');
  });

  it('says what is missing when the conversation was opened from history', async () => {
    held = {};
    chat.messages = [
      { role: 'user', text: 'a site' },
      { role: 'assistant', text: reply },
    ];
    const { usePageCheckStore, replyKey } = await import('./pageCheckStore');
    await usePageCheckStore.getState().check(reply, 'a site');
    expect(usePageCheckStore.getState().byReply[replyKey(reply)].pictures?.join(' ')).toContain(
      'refers to photo-1.jpg, which is not part of it',
    );
  });
});
