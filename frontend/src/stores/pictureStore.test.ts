/**
 * @vitest-environment jsdom
 *
 * The pictures a page uses come from the backend by attachment id, as data: URIs,
 * and "gone" is told apart from "could not ask".
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { usePictureStore } from './pictureStore';

const fetchMock = vi.fn();

beforeEach(() => {
  usePictureStore.setState({ held: {} });
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});

const png = () =>
  new Response(new Uint8Array([0x89, 0x50, 0x4e, 0x47]), { status: 200, headers: { 'content-type': 'image/png' } });

describe('a picture the session no longer holds but its conversation kept', () => {
  const calls = () => fetchMock.mock.calls.map((c) => String(c[0]));

  it('is fetched from the kept copy when the live one is gone', async () => {
    fetchMock
      .mockResolvedValueOnce(new Response('{}', { status: 404 }))
      .mockResolvedValueOnce(png());
    await usePictureStore.getState().ensure('new session', ['att_1'], 'conv_1');
    expect(calls()[0]).toContain('/chat/attachments/att_1/content');
    expect(calls()[1]).toContain('/conversations/conv_1/pictures/att_1');
    expect(usePictureStore.getState().held.att_1).toBe('data:image/png;base64,iVBORw==');
  });

  it('is gone only when the session and the conversation both say so', async () => {
    fetchMock.mockResolvedValue(new Response('{}', { status: 404 }));
    await usePictureStore.getState().ensure('s', ['att_1'], 'conv_1');
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(usePictureStore.getState().held).toEqual({ att_1: null });
  });

  it('is not asked of a conversation when there is none', async () => {
    fetchMock.mockResolvedValue(new Response('{}', { status: 404 }));
    await usePictureStore.getState().ensure('s', ['att_1'], null);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(usePictureStore.getState().held).toEqual({ att_1: null });
  });

  it('is not called gone when the kept copy could not be reached', async () => {
    fetchMock
      .mockResolvedValueOnce(new Response('{}', { status: 404 }))
      .mockResolvedValueOnce(new Response('{}', { status: 500 }));
    await usePictureStore.getState().ensure('s', ['att_1'], 'conv_1');
    expect('att_1' in usePictureStore.getState().held).toBe(false);
  });

  it('is not fetched from the conversation when the session still has it', async () => {
    fetchMock.mockResolvedValue(png());
    await usePictureStore.getState().ensure('s', ['att_1'], 'conv_1');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe('fetching an attached picture for a page', () => {
  it('holds it as a data: URI, asking for the conversation it belongs to', async () => {
    fetchMock.mockResolvedValue(png());
    await usePictureStore.getState().ensure('s 1', ['att_1']);
    expect(String(fetchMock.mock.calls[0][0])).toContain('/chat/attachments/att_1/content?session_id=s%201');
    expect(usePictureStore.getState().held.att_1).toBe(`data:image/png;base64,${btoa('PNG')}`);
  });

  it('asks once however many times it is asked', async () => {
    fetchMock.mockResolvedValue(png());
    await Promise.all([
      usePictureStore.getState().ensure('s', ['att_1']),
      usePictureStore.getState().ensure('s', ['att_1']),
    ]);
    await usePictureStore.getState().ensure('s', ['att_1']);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('records a picture the backend no longer has as gone', async () => {
    fetchMock.mockResolvedValue(new Response('{}', { status: 404 }));
    await usePictureStore.getState().ensure('s', ['att_1']);
    expect(usePictureStore.getState().held).toEqual({ att_1: null });
  });

  it('does not call a picture gone because the backend could not be reached', async () => {
    fetchMock.mockRejectedValueOnce(new Error('network'));
    await usePictureStore.getState().ensure('s', ['att_1']);
    expect('att_1' in usePictureStore.getState().held).toBe(false);
    fetchMock.mockResolvedValueOnce(png());
    await usePictureStore.getState().ensure('s', ['att_1']);
    expect(usePictureStore.getState().held.att_1).toMatch(/^data:image\/png/);
  });
});
