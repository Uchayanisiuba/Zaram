/**
 * @vitest-environment jsdom
 *
 * Watching Zaram drive the app: one card, and what it just did.
 *
 * Asked for on 3 October 2026 — a card for the app, openable, with the
 * steps underneath.
 *
 * The card already existed for `start_app`. Driving added two problems it
 * did not have. Every driving call reports the page it is on, which is what
 * lets the card follow Zaram around the app and would also give **a card
 * per click** — a reply that pressed six buttons rendering six copies of
 * the same panel. And the card said "running at", which describes the dev
 * server at the moment the interesting thing is the browser.
 *
 * Both are assertions about what a person sees, not about how it is built,
 * so a different fix that delivers them still passes.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('@/services/toolsClient', () => ({
  grantTool: vi.fn(),
  allowToolForSession: vi.fn(),
}));
vi.mock('@/stores/chatStore', () => ({
  useChatStore: (selector: (s: { sessionId: string; projectId: string }) => unknown) =>
    selector({ sessionId: 'session-1', projectId: 'ride-share' }),
}));
vi.mock('@/stores/projectStore', () => ({
  useProjectStore: (selector: (s: { stopApp: () => Promise<boolean> }) => unknown) =>
    selector({ stopApp: async () => true }),
}));

import ToolCalls from './ToolCalls';
import type { ChatToolCall } from '../../stores/chatStore';

const drove = (over: Partial<ChatToolCall> = {}): ChatToolCall => ({
  server: 'code',
  tool: 'click_in_app',
  verdict: 'allow',
  reason: '',
  target: 'clicked Create',
  appUrl: 'http://localhost:5173/',
  ...over,
});

describe('the live pane', () => {
  it('shows one card however many times the app was driven', () => {
    render(
      <ToolCalls
        calls={[
          drove({ tool: 'open_in_browser', target: 'opened http://localhost:5173/' }),
          drove({ target: 'clicked Coding' }),
          drove({ tool: 'type_in_app', target: "typed 'C:/RideShare' into Repository folder" }),
          drove({ target: 'clicked Create' }),
        ]}
      />,
    );
    expect(screen.getAllByTestId('app-card')).toHaveLength(1);
  });

  it('shows the page it ended on, not the one it started from', () => {
    render(
      <ToolCalls
        calls={[
          drove({ tool: 'open_in_browser', appUrl: 'http://localhost:5173/' }),
          drove({ appUrl: 'http://localhost:5173/settings' }),
        ]}
      />,
    );
    expect(screen.getByTestId('app-url').textContent).toContain('/settings');
  });

  it('calls it driving rather than running', () => {
    // Both a started server and a driven page carry a URL, and over a page
    // Zaram is clicking through, "running at" describes the wrong half of
    // what is happening.
    render(<ToolCalls calls={[drove()]} />);
    expect(screen.getByTestId('app-card').textContent).toContain('driving');
  });

  it('still calls a started server running', () => {
    render(
      <ToolCalls
        calls={[drove({ tool: 'start_app', target: 'dev', appUrl: 'http://localhost:5173/' })]}
      />,
    );
    expect(screen.getByTestId('app-card').textContent).toContain('running at');
  });

  it('says what it pressed, by name, not by ref', () => {
    // `clicked e5` is Zaram's own bookkeeping. The whole value of watching
    // is knowing which button was pressed.
    //
    // `active` because the steps live in the fold, which stays open while
    // the reply is being written — which is exactly when somebody is
    // watching it happen.
    render(<ToolCalls calls={[drove({ target: 'clicked Create' })]} active />);
    expect(screen.getByText(/clicked Create/)).toBeTruthy();
  });

  it('folds the steps away afterwards without dropping them', () => {
    // One press from a finished transcript. A reply somebody comes back to
    // still has to be able to answer "what did it actually press", and the
    // card above it stays whether the fold is open or not.
    render(<ToolCalls calls={[drove({ target: 'clicked Create' })]} />);
    expect(screen.queryByText(/clicked Create/)).toBeNull();
    expect(screen.getByTestId('app-card')).toBeTruthy();
  });

  it('keeps every screenshot, because each is a separate look', () => {
    // Unlike the URL, a second screenshot is not a duplicate of the first:
    // it is a deliberate look at a different moment.
    render(
      <ToolCalls
        calls={[
          drove({ tool: 'look_at_app', appUrl: '', image: 'one.png' }),
          drove({ tool: 'look_at_app', appUrl: '', image: 'two.png' }),
        ]}
      />,
    );
    expect(screen.getAllByTestId('app-card')).toHaveLength(2);
  });
});
