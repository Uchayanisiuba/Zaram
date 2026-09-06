/**
 * A task Zaram stopped partway through has to be findable, and continuable.
 *
 * The button under a reply was never enough on its own: that reply is gone the
 * moment the app closes, and *"stop on Tuesday, carry on Thursday"* is the whole
 * reason the task is written down. So Project lists what is waiting, and this
 * asserts the two things that make the list worth having — the press reaches the
 * backend as a continuation of **that** task, and nothing is shown when nothing
 * is waiting.
 *
 * **Why it drives `ProjectWorkspace` rather than a lifted component.** A list
 * that renders and calls nothing is exactly the shape `NoticeCard.test.tsx`
 * warns about: `onOpen` was wired to a store with no readers, every unit test
 * passed, and the button did nothing for a fortnight. The wiring is the claim.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import ProjectWorkspace from './ProjectWorkspace';
import { useChatStore } from '@/stores/chatStore';

const A_TASK = {
  id: 'plan-1',
  question: 'what does resident_budget_bytes return',
  project_id: 'northwind',
  model: 'qwen3-14b-16k',
  stopped_because: 'Zaram stopped after 12 tool calls.',
  steps: [
    { server: 'code', tool: 'search_code' },
    { server: 'code', tool: 'read_lines' },
  ],
  created_at: 1,
  updated_at: 2,
};

function respond(plans: unknown[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/plans')) {
        return new Response(JSON.stringify({ plans, kept_for_days: 7 }), { status: 200 });
      }
      // Project's own loads. An empty answer is enough: this file is about the
      // unfinished list, and a failing project fetch would fail it for the
      // wrong reason.
      return new Response(JSON.stringify({ projects: [], unclaimed: [] }), { status: 200 });
    }),
  );
}

describe('unfinished tasks in Project', () => {
  beforeEach(() => {
    useChatStore.setState({ isStreaming: false, messages: [] });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('lists what is waiting, with what it did and why it stopped', async () => {
    respond([A_TASK]);

    render(<ProjectWorkspace />);

    expect(
      await screen.findByText('what does resident_budget_bytes return'),
    ).toBeTruthy();
    expect(screen.getByText(/search_code, read_lines/)).toBeTruthy();
    expect(screen.getByText(/Kept for\s+7\s+days/)).toBeTruthy();
  });

  it('continues that task, by id, in the conversation', async () => {
    respond([A_TASK]);
    const send = vi.fn().mockResolvedValue(undefined);
    const setProject = vi.fn();
    useChatStore.setState({ send, setProject });
    const openConversation = vi.fn();

    render(<ProjectWorkspace onOpenConversation={openConversation} />);
    fireEvent.click(await screen.findByTestId('resume-task'));

    await waitFor(() =>
      expect(send).toHaveBeenCalledWith('Continue', {
        continueTask: true,
        planId: 'plan-1',
      }),
    );
    // The project travels with it: a coding task resumed outside its project
    // has no folder to read, and its tools would refuse every call.
    expect(setProject).toHaveBeenCalledWith('northwind');
    // And it goes where the answer will appear. A press that streams a reply
    // onto a surface the user is not looking at is the same defect as a button
    // that does nothing.
    expect(openConversation).toHaveBeenCalled();
  });

  it('shows nothing at all when nothing is waiting', async () => {
    respond([]);

    render(<ProjectWorkspace />);

    await waitFor(() => expect(screen.queryByTestId('resume-task')).toBeNull());
    expect(screen.queryByText(/unfinished/i)).toBeNull();
  });
});
