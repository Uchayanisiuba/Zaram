/**
 * The orbit shows every node, and only the nodes.
 *
 * **This exists because a comment did not stop the drift it described.**
 * `registry.ts` calls `orbitOrder` the canonical list and warns, in prose, that
 * TopNav, LeftRail and CommandPalette had each restated it and CommandPalette
 * had silently lost Activity as a result. The lesson was written down and not
 * enforced — and `orbitOrder` ended up with **no consumers at all**, so it was
 * canonical only in its own docstring.
 *
 * The result: adding Project to the registry updated the rail, the command palette and the
 * router, and the orbit — the first thing anyone sees on opening Zaram — kept
 * rendering five nodes. The node was "added" and invisible.
 *
 * A `Record<WorkspaceId, …>` catches a *missing* entry at compile time, which
 * is why the rail and palette broke loudly. A hand-written array cannot be
 * caught that way, so it is caught here.
 */
import { describe, it, expect } from 'vitest';
import { ORBITAL_NODES } from './Landing';
import { orbitOrder, surfaceLabels } from '@/runtime/shortcuts/registry';

describe('the landing orbit', () => {
  it('renders exactly the canonical nodes, in the canonical order', () => {
    expect(ORBITAL_NODES.map((n) => n.id)).toEqual(orbitOrder);
  });

  it('labels them the way the rest of the shell does', () => {
    // A node called "Project" in the orbit and "Projects" in the rail is two
    // names for one place, which is how a user concludes they are different.
    for (const node of ORBITAL_NODES) {
      expect(node.label).toBe(surfaceLabels[node.id as keyof typeof surfaceLabels]);
    }
  });

  it('spaces the nodes evenly around the full circle', () => {
    // The step is written as a constant and the count is derived from the
    // array, so the two can disagree — which shows up as a gap in the ring or
    // two nodes on top of each other, both of which read as a broken render
    // rather than as a missing entry.
    const angles = ORBITAL_NODES.map((n) => n.angle);
    const gaps = angles.map((angle, i) => {
      const next = angles[(i + 1) % angles.length];
      return (next - angle + 360) % 360;
    });

    expect(new Set(gaps).size).toBe(1);
    expect(gaps[0]).toBe(360 / ORBITAL_NODES.length);
  });

  it('gives every node its own colour', () => {
    // Colour is the only thing distinguishing two nodes at a glance on the
    // landing, where the labels are small and the icons are monochrome.
    const colours = ORBITAL_NODES.map((n) => n.color);
    expect(new Set(colours).size).toBe(colours.length);
  });
});
