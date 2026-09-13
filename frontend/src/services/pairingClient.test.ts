/**
 * What the pairing transport must not get wrong: the credential is never in
 * anything this client reads, and a revoked client stays listed as one.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchPairedClients, issuePairingToken, PairingError, revokePairedClient } from './pairingClient';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('the list', () => {
  it('keeps a revoked client, marked, rather than dropping it', async () => {
    fetchMock.mockResolvedValue(
      json({
        clients: [
          { id: 'a', name: 'Claude Code', linked_at: 10, last_seen: 20, revoked_at: null, is_active: true },
          { id: 'b', name: 'Cline', linked_at: 5, last_seen: null, revoked_at: 30, is_active: false },
        ],
      }),
    );
    const clients = await fetchPairedClients();
    expect(clients.map((c) => [c.name, c.isActive])).toEqual([
      ['Claude Code', true],
      ['Cline', false],
    ]);
    expect(clients[1].revokedAt).toBe(30);
    expect(clients[1].lastSeen).toBeNull();
  });

  it('has no field for a credential at all', async () => {
    fetchMock.mockResolvedValue(
      json({ clients: [{ id: 'a', name: 'x', linked_at: 1, is_active: true, credential: 'leaked' }] }),
    );
    const [client] = await fetchPairedClients();
    expect(Object.keys(client)).not.toContain('credential');
  });
});

describe('a token', () => {
  it('comes with its lifetime and the command to run', async () => {
    fetchMock.mockResolvedValue(
      json({ token: 'abc', expires_in: 60, command: 'python -m zaram_mcp pair <token> --name "Claude Code"' }),
    );
    const token = await issuePairingToken();
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'POST' });
    expect(token).toEqual({
      token: 'abc',
      expiresIn: 60,
      command: 'python -m zaram_mcp pair <token> --name "Claude Code"',
    });
  });
});

describe('revoking', () => {
  it('names the client in the path and surfaces a refusal as a message', async () => {
    fetchMock.mockResolvedValue(json({ detail: 'No active client with that id' }, 404));
    await expect(revokePairedClient('a b')).rejects.toBeInstanceOf(PairingError);
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/pairing\/clients\/a%20b$/);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'DELETE' });
  });
});
