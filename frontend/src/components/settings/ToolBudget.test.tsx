/**
 * @vitest-environment jsdom
 *
 * A server the context budget shut out says so, and can be overridden.
 *
 * Found 3 October 2026 by grepping this directory for `offered` — a number the
 * backend has reported per server since 20 September, with **no caller**. So a
 * server offering 39 tools showed 8 and said nothing about the other 31, and
 * the model then truthfully answered that it could not run the thing while the
 * card showed a server that was attached, reachable and healthy.
 *
 * `CLAUDE.md` names both halves: *"disabled capabilities are visible, not
 * silent"*, and the shape underneath it — *"assume unreachable until the caller
 * is seen"*, with fifteen complete, tested, unreachable subsystems already
 * found. The counts were measured, reported and tested. Nothing asked.
 *
 * So these tests are about the **caller**. They render the real section against
 * a stubbed transport, because a unit test of a sentence-formatting helper
 * would have passed for a fortnight exactly as the backend's own tests did.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import ToolsSection from './ToolsSection';

/** `Row` comes from `SettingsWorkspace`; this stands in for it. */
const Row = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>;

const COMFY = {
  id: 'comfy',
  command: ['node', 'comfy.js'],
  url: '',
  transport: 'stdio',
  reachable: true,
  writes: 'host_undo',
  grantedTools: [],
  knownHost: null,
  tools: 39,
  offered: 8,
  toolBudget: 8,
  builtin: false,
  pinnedTools: [] as string[],
};

/** Answers the two endpoints the row uses, and records every PUT. */
function server(overrides: Record<string, unknown> = {}) {
  const pins: string[][] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === 'PUT' && url.includes('/pins')) {
        const body = JSON.parse(String(init.body)) as { tools: string[] };
        pins.push(body.tools);
        return new Response(JSON.stringify({ pinnedTools: body.tools }), { status: 200 });
      }
      if (url.endsWith('/comfy/tools')) {
        return new Response(
          JSON.stringify({
            tools: Array.from({ length: 39 }, (_, n) => ({
              name: `edit_thing_${String(n).padStart(2, '0')}`,
              qualified_name: `comfy:edit_thing_${String(n).padStart(2, '0')}`,
              description: `changes thing ${n}`,
              suspicions: [],
            })),
          }),
          { status: 200 },
        );
      }
      return new Response(
        JSON.stringify({ servers: [{ ...COMFY, ...overrides }] }),
        { status: 200 },
      );
    }),
  );
  return pins;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('what the budget dropped', () => {
  it('says how many did not reach the model, and how much room there is', async () => {
    server();
    render(<ToolsSection Row={Row} />);
    const line = await screen.findByTestId('budget-shortfall-comfy');
    expect(line.textContent).toContain('31 of 39');
    expect(line.textContent).toContain('8 at once');
  });

  it('says nothing when every tool fits', async () => {
    server({ tools: 6, offered: 6 });
    render(<ToolsSection Row={Row} />);
    await screen.findAllByText(/comfy/);
    expect(screen.queryByTestId('budget-shortfall-comfy')).toBeNull();
  });

  it('says nothing before a question has gone through', async () => {
    // `null`, not 0 — "nothing has been asked yet" and "this server was shut
    // out" are different answers, and a warning here would be the invented
    // value CLAUDE.md calls worse than no indicator.
    server({ tools: null, offered: null, toolBudget: null });
    render(<ToolsSection Row={Row} />);
    await screen.findAllByText(/comfy/);
    expect(screen.queryByTestId('budget-shortfall-comfy')).toBeNull();
  });

  it('does not warn about one of Zaram’s own packs', async () => {
    server({ builtin: true });
    render(<ToolsSection Row={Row} />);
    await screen.findAllByText(/comfy/);
    expect(screen.queryByTestId('budget-shortfall-comfy')).toBeNull();
  });
});

describe('choosing which to keep', () => {
  it('asks the server for its names, not for the shortlist', async () => {
    server();
    render(<ToolsSection Row={Row} />);
    fireEvent.click(await screen.findByTestId('budget-shortfall-comfy'));
    // All 39, because the person is here precisely because 8 is not enough.
    await waitFor(() => expect(screen.getByTestId('pin-comfy-edit_thing_38')).toBeTruthy());
    expect(screen.getByTestId('pin-comfy-edit_thing_00')).toBeTruthy();
  });

  it('sends the whole set, so unticking the last one means none', async () => {
    const pins = server({ pinnedTools: ['edit_thing_38'] });
    render(<ToolsSection Row={Row} />);
    fireEvent.click(await screen.findByTestId('budget-shortfall-comfy'));
    const box = await screen.findByTestId('pin-comfy-edit_thing_38');
    expect((box as HTMLInputElement).checked).toBe(true);
    fireEvent.click(box);
    await waitFor(() => expect(pins.length).toBe(1));
    expect(pins[0]).toEqual([]);
  });

  it('adds to what is already pinned rather than replacing it', async () => {
    const pins = server({ pinnedTools: ['edit_thing_38'] });
    render(<ToolsSection Row={Row} />);
    fireEvent.click(await screen.findByTestId('budget-shortfall-comfy'));
    fireEvent.click(await screen.findByTestId('pin-comfy-edit_thing_00'));
    await waitFor(() => expect(pins.length).toBe(1));
    expect(pins[0].sort()).toEqual(['edit_thing_00', 'edit_thing_38']);
  });

  it('says plainly that keeping a tool is not allowing it', async () => {
    // The one thing this control must never be read as. Being seen by the
    // model and being allowed to act are different questions, and the
    // sentence has to say so where the checkbox is.
    server();
    render(<ToolsSection Row={Row} />);
    fireEvent.click(await screen.findByTestId('budget-shortfall-comfy'));
    await waitFor(() =>
      expect(screen.getByText(/only means the model gets to see it/i)).toBeTruthy(),
    );
  });

  it('a failed listing says so instead of showing an empty list', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/comfy/tools')) {
          return new Response(JSON.stringify({ detail: 'the server stopped answering' }), {
            status: 503,
          });
        }
        return new Response(JSON.stringify({ servers: [COMFY] }), { status: 200 });
      }),
    );
    render(<ToolsSection Row={Row} />);
    fireEvent.click(await screen.findByTestId('budget-shortfall-comfy'));
    await waitFor(() => expect(screen.getByText(/stopped answering/i)).toBeTruthy());
    expect(screen.queryByTestId('pin-comfy-edit_thing_00')).toBeNull();
  });
});

describe('a server that fits but has pins', () => {
  /** The other branch. Replacing every `budget-pinned-comfy` with
   *  `budget-shortfall-comfy` while fixing the selectors above left this one
   *  with no caller — the exact shape this whole file is about, so it is
   *  worth one test rather than a note. */
  it('still says what it is keeping, and lets it be changed', async () => {
    const pins = server({ tools: 6, offered: 6, pinnedTools: ['edit_thing_00'] });
    render(<ToolsSection Row={Row} />);
    const line = await screen.findByTestId('budget-pinned-comfy');
    expect(line.textContent).toContain('Keeping 1 tool');
    expect(line.textContent).not.toContain('Keeping 1 tools');
    expect(screen.queryByTestId('budget-shortfall-comfy')).toBeNull();

    fireEvent.click(line);
    fireEvent.click(await screen.findByTestId('pin-comfy-edit_thing_00'));
    await waitFor(() => expect(pins.length).toBe(1));
    expect(pins[0]).toEqual([]);
  });
});
