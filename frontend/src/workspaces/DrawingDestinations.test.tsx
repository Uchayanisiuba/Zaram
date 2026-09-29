/**
 * @vitest-environment jsdom
 *
 * A destination Zaram can draw at has somewhere to be said yes to.
 *
 * Reported 29 September 2026 as *"the cloud image gen isn't working"*. The
 * refusal was already saying the right sentence —
 *
 *     Allow images to image.pollinations.ai under Activity → Destinations,
 *     and ask again.
 *
 * — and that row was not on that screen. `GET /egress/policy` returns hosts
 * *seen*, and Pollinations is refused at `availability()` before it sends, so
 * it is never contacted, never logged, never listed, never grantable. Measured
 * on the maintainer's machine: `image.pollinations.ai` appeared in neither
 * `hosts_seen` nor `rules`.
 *
 * Two gates, each correct about a different host and both wrong about this
 * one: the list was `hostsSeen ∪ rules`, and the images control rendered only
 * `if policy?.rules[h]`, reasoned as *"offering to permit pictures to
 * somewhere nothing may be sent is a control that governs nothing."* True of
 * an arbitrary host. Inverted for one Zaram draws at, because `policy.decide`
 * consults the class rules whenever the host rule is not `deny`.
 *
 * Driving `ActivityWorkspace` rather than the client alone, because the claim
 * is that there is a **button** — and a transport that carries the host to a
 * surface which does not render it is the bug this had in the first place.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import ActivityWorkspace from './ActivityWorkspace';

/** The maintainer's real state: NIM contacted and ruled, Pollinations neither. */
const POLICY = {
  default: 'deny',
  rules: { 'ai.api.nvidia.com': 'ask' },
  class_rules: {},
  hosts_seen: ['ai.api.nvidia.com'],
  hosts_without_a_rule: [],
  can_draw_at: [
    { host: 'ai.api.nvidia.com', what: 'flux-schnell · NVIDIA NIM', needs_key: 'yes' },
    { host: 'image.pollinations.ai', what: 'flux · Pollinations', needs_key: '' },
  ],
};

function server(policy: unknown = POLICY) {
  const sent: { url: string; method?: string; body: any }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      sent.push({
        url,
        method: init?.method,
        body: init?.body ? JSON.parse(String(init.body)) : undefined,
      });
      if (url.includes('/egress/policy')) {
        return new Response(JSON.stringify(policy), { status: 200 });
      }
      // Activity's other loads. Empty-but-present is enough; this file is
      // about the destinations list, and a sibling fetch that renders nothing
      // would fail it for the wrong reason. The keys are the array-shaped
      // ones its children destructure — a missing array is a crash, not an
      // empty section.
      return new Response(
        JSON.stringify({
          entries: [],
          intact: true,
          tasks: [],
          finished: [],
          plans: [],
          triggers: [],
          runs: [],
          kinds: [],
          obligations: [],
          questions: [],
          sources: [],
          kept_for_days: 7,
        }),
        { status: 200 },
      );
    }),
  );
  return sent;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('a destination Zaram can draw at', () => {
  it('is listed even though nothing has ever been sent to it', async () => {
    server();
    render(<ActivityWorkspace />);
    expect(await screen.findByText('image.pollinations.ai')).toBeTruthy();
  });

  it('offers the images control without needing a host rule first', async () => {
    // The second gate. `image.pollinations.ai` has no entry in `rules`, and
    // the row used to render only for hosts that did — so the host could be
    // listed and still have no way to grant pictures.
    server();
    render(<ActivityWorkspace />);
    await screen.findByText('image.pollinations.ai');

    const rows = screen.getAllByText('images');
    expect(rows.length).toBeGreaterThanOrEqual(2);
  });

  it('sends the grant for the image class, not for prompts', async () => {
    // Rule 7j: consent is per destination *and* data class. Granting pictures
    // must not quietly grant the chat path to the same host.
    const sent = server();
    render(<ActivityWorkspace />);
    await screen.findByText('image.pollinations.ai');

    const allows = screen.getAllByRole('button', { name: /^allow$/i });
    fireEvent.click(allows[allows.length - 1]);

    await waitFor(() => {
      const put = sent.find((s) => s.method === 'PUT');
      expect(put?.body?.data_class).toBe('image');
      expect(put?.body?.mode).toBe('allow');
    });
  });

  it('claims nothing when an older backend does not send the list', async () => {
    // Absent is not "Zaram can draw nowhere". Rendering a claim on a field
    // that was never sent is the one thing a privacy surface may not do.
    server({ ...POLICY, can_draw_at: undefined });
    render(<ActivityWorkspace />);
    await screen.findByText('ai.api.nvidia.com');
    expect(screen.queryByText('image.pollinations.ai')).toBeNull();
  });
});
