/**
 * Work's layout, and the promise it must not break while gaining one.
 *
 * The rebuild added search, grouping, sorting, aligned columns and a density
 * toggle. All of that is furniture, and furniture is a judgement — what is
 * asserted here is the one thing that is not: **Work is not a file browser.**
 * `CLAUDE.md` says so in as many words — *"every row carries the conversation
 * that produced it. Strip that and this is a file browser, and the operating
 * system already ships one"* — and a layout pass is exactly the change that
 * quietly drops it, because the conversation is the least column-shaped thing
 * on the row.
 *
 * The grouping and sorting rules live in `organise.test.ts`, where they can be
 * walked across a date boundary without rendering anything.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import type { Artifact } from '@/services/artifactsClient';

const listArtifacts = vi.fn();
const deleteArtifacts = vi.fn();
const restoreArtifacts = vi.fn();

vi.mock('@/services/artifactsClient', async () => {
  const actual = await vi.importActual<typeof import('@/services/artifactsClient')>(
    '@/services/artifactsClient',
  );
  return {
    ...actual,
    listArtifacts: (...args: unknown[]) => listArtifacts(...(args as [])),
    getArtifact: vi.fn(async () => null),
    downloadArtifact: vi.fn(async () => undefined),
    deleteArtifacts: (...args: unknown[]) => deleteArtifacts(...(args as [])),
    restoreArtifacts: (...args: unknown[]) => restoreArtifacts(...(args as [])),
  };
});

vi.mock('@/hooks/useArtifactImage', () => ({
  useArtifactImage: () => ({ url: null, error: null }),
}));

import WorkWorkspace from '../WorkWorkspace';

const now = Date.now() / 1000;

function art(over: Partial<Artifact> & { id: string }): Artifact {
  return {
    filename: `${over.id}.pdf`,
    kind: 'document',
    project_id: '',
    origin: 'generated',
    created_at: now,
    size_bytes: 2048,
    path: null,
    conversation_id: 'c1',
    conversation_title: '',
    sources: [],
    claims: [],
    indexed: true,
    remember_override: null,
    exists: true,
    ...over,
  } as Artifact;
}

const ROWS = [
  art({
    id: 'inv',
    filename: 'invoice-0007.pdf',
    kind: 'invoice',
    project_id: 'northwind',
    conversation_title: 'Northwind rate change',
  }),
  art({
    id: 'doc',
    filename: 'brief.docx',
    kind: 'document',
    project_id: 'acme',
    conversation_title: 'Acme kickoff',
  }),
  art({
    id: 'pic',
    filename: 'logo-2.png',
    kind: 'image',
    conversation_title: 'Logo ideas',
  }),
];

beforeEach(() => {
  listArtifacts.mockReset();
  listArtifacts.mockResolvedValue({ artifacts: ROWS });
  deleteArtifacts.mockReset();
  deleteArtifacts.mockResolvedValue({
    removed: [{ id: 'inv', filename: 'invoice-0007.pdf' }],
    skipped: [],
    note: 'Moved to the trash folder beside your work. Anything Zaram remembered stays in Memory until you remove it there.',
  });
  restoreArtifacts.mockReset();
  restoreArtifacts.mockResolvedValue({ restored: [{ id: 'inv', filename: 'invoice-0007.pdf' }], skipped: [] });
});

afterEach(cleanup);

const user = () => userEvent.setup();

describe('it is not a file browser', () => {
  it('shows the conversation that produced each file', async () => {
    // The whole reason this surface exists rather than deferring to the
    // operating system's own file view.
    render(<WorkWorkspace />);

    expect(await screen.findByText('Northwind rate change')).toBeInTheDocument();
    expect(screen.getByText('Acme kickoff')).toBeInTheDocument();
  });

  it('says so when a file has no conversation, rather than showing a blank', async () => {
    listArtifacts.mockResolvedValue({ artifacts: [art({ id: 'orphan' })] });
    render(<WorkWorkspace />);

    expect(await screen.findByText(/no conversation recorded/i)).toBeInTheDocument();
  });

  it('finds a file by the conversation that made it', async () => {
    render(<WorkWorkspace />);
    await screen.findByText('invoice-0007.pdf');

    await user().type(screen.getByRole('searchbox', { name: /search/i }), 'northwind');

    expect(screen.getByText('invoice-0007.pdf')).toBeInTheDocument();
    expect(screen.queryByText('brief.docx')).not.toBeInTheDocument();
  });
});

describe('files are categorised', () => {
  it('groups by type by default, with a heading and a count', async () => {
    render(<WorkWorkspace />);

    // The headings a person means when they say their files are not organised.
    expect(await screen.findByRole('heading', { name: /invoices/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /documents/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /images/i })).toBeInTheDocument();
  });

  it('regroups by project without touching what is shown', async () => {
    render(<WorkWorkspace />);
    await screen.findByRole('heading', { name: /invoices/i });

    await user().selectOptions(screen.getByLabelText('Group by'), 'project');

    expect(screen.getByRole('heading', { name: /acme/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /northwind/i })).toBeInTheDocument();
    // Nothing was filtered away by regrouping — a group is a cut of the same
    // set, not a place a file was moved to.
    expect(screen.getByText('invoice-0007.pdf')).toBeInTheDocument();
    expect(screen.getByText('brief.docx')).toBeInTheDocument();
    expect(screen.getByText('logo-2.png')).toBeInTheDocument();
  });

  it('can be turned off', async () => {
    render(<WorkWorkspace />);
    await screen.findByRole('heading', { name: /invoices/i });

    await user().selectOptions(screen.getByLabelText('Group by'), 'none');

    expect(screen.queryByRole('heading', { name: /invoices/i })).not.toBeInTheDocument();
    expect(screen.getByText('invoice-0007.pdf')).toBeInTheDocument();
  });

  it('shows no heading for a type nobody has made', async () => {
    // An empty heading claims the bucket exists and is empty, which on this
    // surface reads as "your spreadsheets are gone".
    render(<WorkWorkspace />);
    await screen.findByRole('heading', { name: /invoices/i });

    expect(screen.queryByRole('heading', { name: /spreadsheets/i })).not.toBeInTheDocument();
  });
});

describe('the toolbar', () => {
  it('offers every type with a live count, including the empty ones', async () => {
    // A count on a filter is what lets an empty one say so before it is
    // clicked — which is the opposite failure to an empty heading, and why one
    // is a chip and the other is not.
    render(<WorkWorkspace />);

    const spreadsheets = await screen.findByRole('button', { name: /spreadsheets/i });
    expect(within(spreadsheets).getByText('0')).toBeInTheDocument();
  });

  it('narrows to one type', async () => {
    render(<WorkWorkspace />);
    await screen.findByText('invoice-0007.pdf');

    await user().click(screen.getByRole('button', { name: /^invoices/i }));

    expect(screen.getByText('invoice-0007.pdf')).toBeInTheDocument();
    expect(screen.queryByText('brief.docx')).not.toBeInTheDocument();
  });

  it('reports which density is in effect, not only which was chosen', async () => {
    // `auto` is the default, so neither button was ever pressed — a toggle
    // that left both unlit would be a control that does not report the state
    // it governs.
    render(<WorkWorkspace />);
    await screen.findByText('invoice-0007.pdf');

    expect(screen.getByRole('button', { name: /show as a list/i })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('button', { name: /show as a grid/i })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('lets the user overrule the automatic density', async () => {
    render(<WorkWorkspace />);
    await screen.findByText('invoice-0007.pdf');

    await user().click(screen.getByRole('button', { name: /show as a grid/i }));

    expect(screen.getByRole('button', { name: /show as a grid/i })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });
});

describe('when there is nothing to show', () => {
  it('offers a way back out of a filter that matches nothing', async () => {
    render(<WorkWorkspace />);
    await screen.findByText('invoice-0007.pdf');

    await user().type(screen.getByRole('searchbox', { name: /search/i }), 'zzzznothing');

    // Never a dead end. The search is a filter like any other, so the same
    // recovery action has to clear it — an empty state that offered to clear
    // the chips and left the query in place would be a dead end wearing a
    // button.
    expect(await screen.findByText(/nothing matches those filters/i)).toBeInTheDocument();
    await user().click(screen.getByRole('button', { name: 'Clear filters' }));

    expect(screen.getByText('invoice-0007.pdf')).toBeInTheDocument();
  });

  it('says what to do when nothing has been made at all', async () => {
    listArtifacts.mockResolvedValue({ artifacts: [] });
    render(<WorkWorkspace />);

    expect(await screen.findByText(/nothing here yet/i)).toBeInTheDocument();
  });
});

describe('selecting and removing', () => {
  it('selects one file at a time', async () => {
    render(<WorkWorkspace />);
    await screen.findByText('invoice-0007.pdf');

    await user().click(screen.getByRole('checkbox', { name: /select invoice-0007\.pdf/i }));

    expect(await screen.findByText('1 file selected')).toBeInTheDocument();
  });

  it('selects a whole group at once, which is select-by-project', async () => {
    // Not a separate menu. The grouping already cuts the listing by project,
    // so the heading's checkbox *is* select-by-project — and under "group by
    // date" the same control is select-by-date.
    render(<WorkWorkspace />);
    await screen.findByRole('heading', { name: /invoices/i });

    await user().selectOptions(screen.getByLabelText('Group by'), 'project');
    await user().click(
      screen.getByRole('checkbox', { name: /select everything under northwind/i }),
    );

    expect(await screen.findByText('1 file selected')).toBeInTheDocument();
  });

  it('selects by date under the date grouping', async () => {
    render(<WorkWorkspace />);
    await screen.findByRole('heading', { name: /invoices/i });

    await user().selectOptions(screen.getByLabelText('Group by'), 'date');
    await user().click(screen.getByRole('checkbox', { name: /select everything under today/i }));

    expect(await screen.findByText('3 files selected')).toBeInTheDocument();
  });

  it('unticks a group that is already fully ticked', async () => {
    render(<WorkWorkspace />);
    await screen.findByRole('heading', { name: /invoices/i });

    const heading = screen.getByRole('checkbox', { name: /select everything under invoices/i });
    await user().click(heading);
    expect(await screen.findByText('1 file selected')).toBeInTheDocument();

    await user().click(heading);
    expect(screen.queryByText(/file selected/)).not.toBeInTheDocument();
  });

  it('asks before it removes anything', async () => {
    // Rule 6, and the tier table: mutative needs a confirm. A selection of
    // forty files removed by a mis-click is what this is for.
    render(<WorkWorkspace />);
    await screen.findByText('invoice-0007.pdf');
    await user().click(screen.getByRole('checkbox', { name: /select invoice-0007\.pdf/i }));

    await user().click(screen.getByRole('button', { name: /^remove$/i }));

    expect(deleteArtifacts).not.toHaveBeenCalled();
    // And it says what will happen rather than asking for certainty.
    expect(screen.getByText(/move to a trash folder/i)).toBeInTheDocument();
  });

  it('removes only on the second, explicit press', async () => {
    render(<WorkWorkspace />);
    await screen.findByText('invoice-0007.pdf');
    await user().click(screen.getByRole('checkbox', { name: /select invoice-0007\.pdf/i }));
    await user().click(screen.getByRole('button', { name: /^remove$/i }));

    await user().click(screen.getByRole('button', { name: /remove 1 file/i }));

    expect(deleteArtifacts).toHaveBeenCalledWith(['inv']);
  });

  it('cancelling leaves the selection alone', async () => {
    render(<WorkWorkspace />);
    await screen.findByText('invoice-0007.pdf');
    await user().click(screen.getByRole('checkbox', { name: /select invoice-0007\.pdf/i }));
    await user().click(screen.getByRole('button', { name: /^remove$/i }));

    await user().click(screen.getByRole('button', { name: /cancel/i }));

    expect(deleteArtifacts).not.toHaveBeenCalled();
    expect(screen.getByText('1 file selected')).toBeInTheDocument();
  });

  it('offers to undo, and says what removal did not touch', async () => {
    render(<WorkWorkspace />);
    await screen.findByText('invoice-0007.pdf');
    await user().click(screen.getByRole('checkbox', { name: /select invoice-0007\.pdf/i }));
    await user().click(screen.getByRole('button', { name: /^remove$/i }));
    await user().click(screen.getByRole('button', { name: /remove 1 file/i }));

    expect(await screen.findByRole('button', { name: /undo/i })).toBeInTheDocument();
    // The backend's own sentence, rendered as it stands.
    expect(screen.getByText(/stays in Memory/i)).toBeInTheDocument();
  });

  it('puts them back on undo', async () => {
    render(<WorkWorkspace />);
    await screen.findByText('invoice-0007.pdf');
    await user().click(screen.getByRole('checkbox', { name: /select invoice-0007\.pdf/i }));
    await user().click(screen.getByRole('button', { name: /^remove$/i }));
    await user().click(screen.getByRole('button', { name: /remove 1 file/i }));

    await user().click(await screen.findByRole('button', { name: /undo/i }));

    expect(restoreArtifacts).toHaveBeenCalledWith(['inv']);
  });

  it('shows what could not be removed rather than swallowing it', async () => {
    // A partial result the user cannot see is a partial result they discover
    // by missing something.
    deleteArtifacts.mockResolvedValue({
      removed: [],
      skipped: [{ id: 'inv', reason: 'invoice-0007.pdf is not where Zaram left it' }],
      note: 'nothing moved',
    });
    render(<WorkWorkspace />);
    await screen.findByText('invoice-0007.pdf');
    await user().click(screen.getByRole('checkbox', { name: /select invoice-0007\.pdf/i }));
    await user().click(screen.getByRole('button', { name: /^remove$/i }));
    await user().click(screen.getByRole('button', { name: /remove 1 file/i }));

    expect(await screen.findByText(/not where Zaram left it/i)).toBeInTheDocument();
  });

  it('shows no selection strip until something is selected', () => {
    // A permanent "0 selected" is a permanent instruction to select something,
    // and it costs the listing a line on every visit.
    render(<WorkWorkspace />);
    expect(screen.queryByText(/selected/i)).not.toBeInTheDocument();
  });
});
