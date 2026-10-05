/**
 * @vitest-environment jsdom
 *
 * A page is run before the person has to, fixed at most twice, and every
 * outcome is said — including "could not check", which is not a pass.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

const send = vi.fn(async () => {});
const checkPage = vi.fn();

let chat: { isStreaming: boolean; messages: { role: string; text: string }[] } = { isStreaming: false, messages: [] };
vi.mock('@/stores/chatStore', () => ({ useChatStore: { getState: () => ({ send, ...chat }) } }));
vi.mock('@/services/pageCheckClient', () => ({ checkPage: (...a: unknown[]) => checkPage(...a) }));
vi.mock('@/lib/previewFrame', () => ({ buildFrameDoc: vi.fn(async () => '<doc/>') }));

const FENCE = '```';
const page = (body: string) => {
  const reply = `Here you go.\n${FENCE}html\n<html><body><script>${body}</script></body></html>\n${FENCE}\n`;
  latest(reply);
  return reply;
};

const clean = { checked: true, ok: true, hung: false, errors: [], blocked: [], blockedSeconds: 0, problems: [], note: '' };
const broken = (problem: string) => ({ ...clean, ok: false, errors: [problem], problems: [problem] });

/** The reply is the last thing in the conversation, as it is right after it streams. */
function latest(reply: string) {
  chat = { isStreaming: false, messages: [{ role: 'user', text: 'q' }, { role: 'assistant', text: reply }] };
}

async function fresh() {
  vi.resetModules();
  window.localStorage.clear();
  return import('./pageCheckStore');
}

beforeEach(() => {
  send.mockClear();
  checkPage.mockReset();
});

describe('a page that works', () => {
  it('is reported as clean and nothing is asked of the model', async () => {
    const { usePageCheckStore, replyKey } = await fresh();
    checkPage.mockResolvedValue(clean);
    const reply = page('var a = 1;');
    await usePageCheckStore.getState().check(reply, 'make a game');
    expect(usePageCheckStore.getState().byReply[replyKey(reply)].status).toBe('clean');
    expect(send).not.toHaveBeenCalled();
  });

  it('is checked once however often it is asked about', async () => {
    const { usePageCheckStore } = await fresh();
    checkPage.mockResolvedValue(clean);
    const reply = page('var a = 1;');
    await usePageCheckStore.getState().check(reply, 'q');
    await usePageCheckStore.getState().check(reply, 'q');
    expect(checkPage).toHaveBeenCalledTimes(1);
  });

  it('carries a slow start into the line, even though it passed', async () => {
    const { usePageCheckStore, replyKey } = await fresh();
    checkPage.mockResolvedValue({ ...clean, blockedSeconds: 6.6, note: 'the page held still' });
    const reply = page('var a = 1;');
    await usePageCheckStore.getState().check(reply, 'q');
    expect(usePageCheckStore.getState().byReply[replyKey(reply)].slowSeconds).toBe(6.6);
  });
});

describe('a page that does not work', () => {
  it('is sent back to the model with what went wrong, as a revision of that reply', async () => {
    const { usePageCheckStore, replyKey } = await fresh();
    checkPage.mockResolvedValue(broken('startTheGame is not defined (line 3)'));
    const reply = page('startTheGame();');
    await usePageCheckStore.getState().check(reply, 'make a game');
    const state = usePageCheckStore.getState().byReply[replyKey(reply)];
    expect(state.status).toBe('fixing');
    expect(state.attempt).toBe(1);
    expect(send).toHaveBeenCalledTimes(1);
    const [text, opts] = send.mock.calls[0] as unknown as [string, { revise: { question: string; reply: string } }];
    expect(text).toContain('startTheGame is not defined (line 3)');
    expect(text).toContain('did not work');
    expect(opts.revise).toEqual({ question: 'make a game', reply });
  });

  it('is asked for twice, and then handed to the person rather than a third time', async () => {
    const { usePageCheckStore, replyKey } = await fresh();
    checkPage.mockResolvedValue(broken('still broken'));
    const replies: string[] = [];
    for (const body of ['a();', 'b();', 'c();']) {
      const reply = page(body);
      replies.push(reply);
      await usePageCheckStore.getState().check(reply, 'q');
    }
    const states = replies.map((r) => usePageCheckStore.getState().byReply[replyKey(r)]);
    expect(states.map((s) => s.status)).toEqual(['fixing', 'fixing', 'gave-up']);
    expect(states.map((s) => s.attempt)).toEqual([1, 2, 2]);
    expect(send).toHaveBeenCalledTimes(2);
  });

  it('starts counting again after a page that worked', async () => {
    const { usePageCheckStore } = await fresh();
    checkPage.mockResolvedValueOnce(broken('x')).mockResolvedValueOnce(broken('x')).mockResolvedValueOnce(clean);
    await usePageCheckStore.getState().check(page('a();'), 'q');
    await usePageCheckStore.getState().check(page('b();'), 'q');
    await usePageCheckStore.getState().check(page('c();'), 'q');
    checkPage.mockResolvedValue(broken('again'));
    await usePageCheckStore.getState().check(page('d();'), 'q');
    expect(send).toHaveBeenCalledTimes(3);
  });

  it('asks for every file again when the page was an app of several', async () => {
    const { usePageCheckStore } = await fresh();
    checkPage.mockResolvedValue(broken('oops'));
    const app =
      `${FENCE}html index.html\n<html><body><script src="game.js"></script></body></html>\n${FENCE}\n` +
      `${FENCE}js game.js\nboom();\n${FENCE}\n`;
    latest(app);
    await usePageCheckStore.getState().check(app, 'q');
    expect((send.mock.calls[0] as unknown as [string])[0]).toContain('every file again in full');
  });

  it('is read from the source when a loop cannot end, without starting a browser', async () => {
    const { usePageCheckStore, replyKey } = await fresh();
    const reply = page('for (let i = 0; i < 16; i) { draw(i); }');
    await usePageCheckStore.getState().check(reply, 'q');
    expect(checkPage).not.toHaveBeenCalled();
    expect(usePageCheckStore.getState().byReply[replyKey(reply)].status).toBe('fixing');
    expect((send.mock.calls[0] as unknown as [string])[0]).toContain('never changes its counter');
  });
});

describe('when not to ask for a fix', () => {
  it('not for a snippet inside an answer, which was never meant to run alone', async () => {
    const { usePageCheckStore } = await fresh();
    const reply = `Use this:\n${FENCE}html\n<div class="c"><script>missing()</script></div>\n${FENCE}`;
    latest(reply);
    await usePageCheckStore.getState().check(reply, 'how do I centre a div');
    expect(checkPage).not.toHaveBeenCalled();
    expect(send).not.toHaveBeenCalled();
  });

  it('not once the person has asked something else, and the line does not claim it did', async () => {
    const { usePageCheckStore, replyKey } = await fresh();
    checkPage.mockResolvedValue(broken('boom'));
    const reply = page('boom();');
    chat = { isStreaming: true, messages: [...chat.messages, { role: 'user', text: 'something else' }] };
    await usePageCheckStore.getState().check(reply, 'q');
    expect(send).not.toHaveBeenCalled();
    expect(usePageCheckStore.getState().byReply[replyKey(reply)].status).toBe('failed');
  });
});

describe('a page that could not be checked', () => {
  it('says so and is not called clean', async () => {
    const { usePageCheckStore, replyKey } = await fresh();
    checkPage.mockResolvedValue({ ...clean, checked: false, ok: null, note: 'No Chrome or Edge is installed' });
    const reply = page('var a = 1;');
    await usePageCheckStore.getState().check(reply, 'q');
    const state = usePageCheckStore.getState().byReply[replyKey(reply)];
    expect(state.status).toBe('unchecked');
    expect(state.note).toContain('No Chrome');
    expect(send).not.toHaveBeenCalled();
  });
});

describe('what is not checked', () => {
  it('a reply with no page, or only a picture', async () => {
    const { usePageCheckStore } = await fresh();
    await usePageCheckStore.getState().check('Just words.', 'q');
    await usePageCheckStore.getState().check(`${FENCE}svg\n<svg xmlns="http://www.w3.org/2000/svg"></svg>\n${FENCE}`, 'q');
    expect(checkPage).not.toHaveBeenCalled();
    expect(Object.keys(usePageCheckStore.getState().byReply)).toEqual([]);
  });

  it('anything, when the person has turned it off — and the choice is remembered', async () => {
    const { usePageCheckStore } = await fresh();
    usePageCheckStore.getState().setEnabled(false);
    await usePageCheckStore.getState().check(page('a();'), 'q');
    expect(checkPage).not.toHaveBeenCalled();
    expect(window.localStorage.getItem('zaram.pageCheck')).toBe('off');
    vi.resetModules();
    const again = await import('./pageCheckStore');
    expect(again.usePageCheckStore.getState().enabled).toBe(false);
  });
});
