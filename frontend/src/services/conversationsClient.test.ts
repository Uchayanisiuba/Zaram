/**
 * @vitest-environment node
 *
 * The session store's transport, focused on the distinction a query string is
 * most likely to flatten.
 *
 * `projectId` omitted means *every* conversation; `''` means the ones belonging
 * to no project. The backend keeps them apart deliberately — collapsing them is
 * how "show me everything" quietly becomes "show me the unscoped ones" — and a
 * URL is exactly where that survives or dies.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';

import {
  deleteConversation,
  fetchConversation,
  fetchConversations,
  renameConversation,
  ConversationError,
} from './conversationsClient';

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Capture every request and answer each with the same body. */
function capture(body: unknown, status = 200) {
  const seen: Array<{ url: string; init?: RequestInit }> = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      seen.push({ url, init });
      return new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      });
    }),
  );
  return seen;
}

describe('scope survives the query string', () => {
  it('omits the parameter entirely when asking for everything', async () => {
    const seen = capture([]);

    await fetchConversations();

    expect(seen[0].url).not.toContain('project_id');
  });

  it('sends an empty parameter when asking for the unscoped ones', async () => {
    const seen = capture([]);

    await fetchConversations('');

    expect(seen[0].url).toContain('project_id=');
    // Present and empty — not absent, which is the other question.
    const url = new URL(seen[0].url, 'http://localhost');
    expect(url.searchParams.get('project_id')).toBe('');
  });

  it('sends the named project when asked for one', async () => {
    const seen = capture([]);

    await fetchConversations('harbour-lane');

    const url = new URL(seen[0].url, 'http://localhost');
    expect(url.searchParams.get('project_id')).toBe('harbour-lane');
  });

  it('treats null the same as asking for everything', async () => {
    // `projectId` is optional and a caller holding "no active project" as
    // `null` must not accidentally ask the narrow question.
    const seen = capture([]);

    await fetchConversations(null);

    expect(seen[0].url).not.toContain('project_id');
  });
});

describe('reading a transcript', () => {
  it('maps the messages, in order, with their attribution', async () => {
    capture({
      id: 'conv_1',
      title: 'what is my day rate',
      project_id: '',
      created_at: 1,
      updated_at: 2,
      message_count: 2,
      messages: [
        { id: 'm1', seq: 1, role: 'user', text: 'what is my day rate', created_at: 1, model: '', locality: '' },
        {
          id: 'm2',
          seq: 2,
          role: 'assistant',
          text: '400 a day.',
          created_at: 2,
          model: 'gemma4:12b',
          locality: 'local',
        },
      ],
    });

    const conversation = await fetchConversation('conv_1');

    expect(conversation.messages.map((m) => m.text)).toEqual([
      'what is my day rate',
      '400 a day.',
    ]);
    expect(conversation.messages[1].model).toBe('gemma4:12b');
    expect(conversation.messages[1].locality).toBe('local');
  });

  it('survives a conversation with no messages array', async () => {
    // An empty conversation is a real thing, and a body without the key is a
    // backend that changed. Neither should throw in the panel.
    capture({ id: 'conv_1', title: '', project_id: '', created_at: 1, updated_at: 1 });

    const conversation = await fetchConversation('conv_1');

    expect(conversation.messages).toEqual([]);
  });

  it('escapes the id rather than pasting it into the path', async () => {
    const seen = capture({ id: 'x', messages: [] });

    await fetchConversation('conv/../secret');

    expect(seen[0].url).not.toContain('conv/../secret');
    expect(seen[0].url).toContain(encodeURIComponent('conv/../secret'));
  });
});

describe('mutating calls', () => {
  it('carries the client header so the browser must preflight', async () => {
    // Not a credential — CLAUDE.md is explicit about that. What it buys is that
    // deleting someone's transcripts cannot be a simple cross-origin request.
    const seen = capture({ deleted: 'conv_1', note: 'x' });

    await deleteConversation('conv_1');

    expect((seen[0].init?.headers as Record<string, string>)['X-Zaram-Client']).toBe(
      'zaram-ui',
    );
  });

  it('returns the sentence saying what deletion did not do', async () => {
    const note =
      'The transcript is gone. Facts Zaram remembered from it are still in Memory.';
    capture({ deleted: 'conv_1', facts_removed: 0, note });

    expect((await deleteConversation('conv_1')).note).toBe(note);
  });

  it('sends a rename as PATCH', async () => {
    const seen = capture({ id: 'conv_1', title: 'Harbour Lane' });

    await renameConversation('conv_1', 'Harbour Lane');

    expect(seen[0].init?.method).toBe('PATCH');
    expect(JSON.parse(String(seen[0].init?.body)).title).toBe('Harbour Lane');
  });
});

describe('failures keep the backend’s own sentence', () => {
  it('surfaces the detail rather than a generic message', async () => {
    // The refusals are written for a person to read. Replacing them with
    // "Request failed" throws away the part that took the thought.
    capture({ detail: 'A conversation needs a title.' }, 400);

    await expect(renameConversation('conv_1', '  ')).rejects.toThrow(
      'A conversation needs a title.',
    );
  });

  it('carries the status for a caller that needs to tell 404 from 500', async () => {
    capture({ detail: 'No such conversation' }, 404);

    await expect(fetchConversation('conv_nothing')).rejects.toMatchObject({
      status: 404,
    });
    await expect(fetchConversation('conv_nothing')).rejects.toBeInstanceOf(
      ConversationError,
    );
  });
});
