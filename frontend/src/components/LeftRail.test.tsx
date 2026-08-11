/**
 * Every node reachable from the rail, once.
 *
 * **Reported by a user, from a screenshot: two Settings buttons**, three rows
 * apart. `surfaceOrder` contains `settings`, and a second copy was pinned below
 * the divider at the foot — so the same destination was drawn twice and read as
 * two different places.
 *
 * This is the node list drifting for the third time, and the third distinct
 * shape it has taken: CommandPalette silently *lost* Activity, the landing orbit
 * silently *missed* Project, and the rail silently *doubled* Settings. The first
 * two were caught by a `Record<WorkspaceId, …>` and by `Landing.test.ts`.
 * Neither catches a duplicate — a Record proves every node has an entry and says
 * nothing about how many times that entry is rendered.
 *
 * So this asserts the property the other two do not: rendered once, and all of
 * them. It renders rather than inspecting the arrays, because the defect was in
 * what reached the screen and an array can be right while the JSX below it adds
 * one more.
 */
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import LeftRail from './LeftRail';
import { orbitOrder, surfaceLabels } from '@/runtime/shortcuts/registry';

afterEach(cleanup);

/** Buttons are named by `aria-label`, which is present whether or not the rail
 *  is expanded — collapsed, the label is the only thing naming them at all. */
const railButtons = (name: string) => screen.queryAllByRole('button', { name });

describe('the left rail', () => {
  it('draws each node exactly once', () => {
    render(<LeftRail workspace="landing" onNavigate={() => {}} />);

    for (const id of orbitOrder) {
      const label = surfaceLabels[id];
      expect(railButtons(label), `${label} appears ${railButtons(label).length} times`).toHaveLength(1);
    }
  });

  it('still offers the way back to the landing', () => {
    // Called "Home" here rather than "Landing" — it is the only node the rail
    // renames, and without it entering a workspace was a one-way trip.
    render(<LeftRail workspace="work" onNavigate={() => {}} />);

    expect(railButtons('Home')).toHaveLength(1);
  });

  it('marks the current surface for anything that is not looking at colour', () => {
    render(<LeftRail workspace="memory" onNavigate={() => {}} />);

    expect(railButtons('Memory')[0]).toHaveAttribute('aria-current', 'page');
    expect(railButtons('Work')[0]).not.toHaveAttribute('aria-current');
  });
});
