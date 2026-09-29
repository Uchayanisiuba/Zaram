/**
 * @vitest-environment jsdom
 *
 * Settings names what draws, and what is sitting there not drawing.
 *
 * Reported 29 September 2026: *"I installed Qwen Image as a replacement, seems
 * like it didn't replace."* It had not. Discovery took the first usable folder
 * in sorted order, `flux1-schnell-nf4` sorts before `qwen-image`, and the
 * replacement was passed over in silence — the only symptom being that nothing
 * changed.
 *
 * The backend half is asserted next door in
 * `test_the_model_that_draws_is_the_one_you_picked.py`. This is the half that
 * makes it visible to a person, and it drives `SettingsWorkspace` rather than a
 * lifted component for the reason `UnfinishedTasks.test.tsx` gives: a list that
 * renders and calls nothing is how a button does nothing for a fortnight while
 * its unit tests pass. The wiring is the claim.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import SettingsWorkspace from './SettingsWorkspace';

const TWO_MODELS = {
  drawing_with: 'flux1-schnell-nf4',
  chosen: null,
  installed: [
    { name: 'flux1-schnell-nf4', pipeline: 'FluxPipeline', usable: true, why_not: '' },
    {
      name: 'qwen-image',
      pipeline: 'QwenImagePipeline',
      usable: false,
      why_not: 'QwenImagePipeline — Zaram draws locally with FLUX only',
    },
  ],
};

/** Answers every load Settings makes, and records what was sent. */
function server(local: unknown) {
  const sent: { url: string; body: any }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.body) sent.push({ url, body: JSON.parse(String(init.body)) });

      if (url.includes('/images/setting')) {
        return new Response(
          JSON.stringify({
            prefer: 'local',
            local_ok: true,
            local,
            cloud: [],
            can: { references: 0, transparent: false },
            answers: 'flux1-schnell-nf4',
          }),
          { status: 200 },
        );
      }
      // Settings' other loads. An empty answer is enough: this file is about
      // the model list, and a failing sibling fetch would fail it for the
      // wrong reason.
      return new Response(JSON.stringify({}), { status: 200 });
    }),
  );
  return sent;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('the image models on this machine', () => {
  it('names the one that is drawing', async () => {
    server(TWO_MODELS);
    render(<SettingsWorkspace />);

    const row = await screen.findByTestId('image-model-flux1-schnell-nf4');
    expect(row.textContent).toContain('drawing with this');
  });

  it('shows the one that is installed and not being used, with why', async () => {
    // The whole report, in one assertion. Before this, nothing on any surface
    // mentioned that a second model was there at all.
    server(TWO_MODELS);
    render(<SettingsWorkspace />);

    const row = await screen.findByTestId('image-model-qwen-image');
    expect(row.textContent).toContain('qwen-image');
    expect(row.textContent).toContain('FLUX');
  });

  it('offers no picker when only one model can draw', async () => {
    // Rule 7h: never make the user choose in advance. A picker with one
    // answer is a question nobody should be asked.
    server(TWO_MODELS);
    render(<SettingsWorkspace />);

    await screen.findByTestId('image-model-qwen-image');
    expect(screen.queryByTestId('image-model-pick')).toBeNull();
  });

  it('offers a picker once two of them can draw, and sends the pick', async () => {
    const sent = server({
      drawing_with: 'a-flux',
      chosen: null,
      installed: [
        { name: 'a-flux', pipeline: 'FluxPipeline', usable: true, why_not: '' },
        { name: 'b-flux', pipeline: 'FluxPipeline', usable: true, why_not: '' },
      ],
    });
    render(<SettingsWorkspace />);

    const pick = await screen.findByTestId('image-model-pick');
    fireEvent.change(pick, { target: { value: 'b-flux' } });

    await waitFor(() => {
      const post = sent.find((s) => s.body?.model !== undefined);
      expect(post?.body).toEqual({ model: 'b-flux' });
      expect(post?.url).toContain('/images/setting');
    });
  });

  it('says nothing at all when the backend reported no models', async () => {
    // Absent is not the same as none. A surface that renders "no models
    // installed" on the strength of a field that was never sent is inventing
    // a value, which is the one thing a status surface may not do.
    server(undefined);
    render(<SettingsWorkspace />);

    await waitFor(() => expect(screen.queryByTestId('image-drawers')).toBeTruthy());
    expect(screen.queryByTestId('image-models')).toBeNull();
  });
});
