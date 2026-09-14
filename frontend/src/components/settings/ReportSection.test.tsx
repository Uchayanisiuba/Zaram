import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import ReportSection from './ReportSection';

function Row({
  label,
  value,
  detail,
  children,
}: {
  label: string;
  value?: string;
  detail?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div>
      <span>{label}</span>
      {value && <em>{value}</em>}
      <div>{detail}</div>
      {children}
    </div>
  );
}

describe('Report a problem', () => {
  it('builds the report, copies it, and shows exactly what was copied', async () => {
    const copy = vi.fn().mockResolvedValue(undefined);
    const load = vi.fn().mockResolvedValue('Zaram 0.1.0 — problem report\nContains no conversation text');
    render(<ReportSection Row={Row} load={load} copy={copy} />);

    await userEvent.click(screen.getByTestId('report-copy'));

    await waitFor(() => expect(copy).toHaveBeenCalledWith(expect.stringContaining('Zaram 0.1.0')));
    expect(screen.getByText('copied')).toBeInTheDocument();
    await userEvent.click(screen.getByTestId('report-toggle'));
    expect(screen.getByTestId('report-text').textContent).toContain('Contains no conversation text');
  });

  it('says where to paste it, and what it does not contain', () => {
    render(<ReportSection Row={Row} load={vi.fn()} copy={vi.fn()} />);
    expect(screen.getByRole('link', { name: /github\.com\/Uchayanisiuba\/Zaram\/issues/i })).toBeInTheDocument();
    expect(screen.getByText(/no conversation, no document names, no remembered facts, no keys/i)).toBeInTheDocument();
  });

  it('a failure is said, not swallowed', async () => {
    render(
      <ReportSection Row={Row} load={vi.fn().mockRejectedValue(new Error('503 Service Unavailable'))} copy={vi.fn()} />,
    );
    await userEvent.click(screen.getByTestId('report-copy'));
    expect(await screen.findByText('503 Service Unavailable')).toBeInTheDocument();
  });
});
