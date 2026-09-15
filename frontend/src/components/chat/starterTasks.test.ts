/**
 * The rules the starter rows rest on, tested without a DOM.
 *
 * The dot is a claim about this machine — "this works right now" — and the
 * only way it stays honest is if an unread signal can never light it. That is
 * the first test here, and it is the one that matters: every other failure
 * shows a row that does nothing, while this one tells somebody a capability is
 * ready when nothing measured it.
 */
import { describe, it, expect } from 'vitest';
import { starterTasks, fillTo, type Capabilities } from './starterTasks';

const NOTHING: Capabilities = { model: false, documents: false, tools: false };
const EVERYTHING: Capabilities = { model: true, documents: true, tools: true };

describe('starterTasks', () => {
  it('lights a row only when its own requirement was measured as met', () => {
    const tasks = starterTasks({ model: true, documents: false, tools: false });
    const byNeed = Object.fromEntries(tasks.map((t) => [t.needs, t.ready]));
    expect(byNeed.model).toBe(true);
    expect(byNeed.documents).toBe(false);
    expect(byNeed.tools).toBe(false);
  });

  it('lights nothing on a machine where nothing could be read', () => {
    // The caller passes `false` for a fetch that failed, so this is also the
    // engine-is-down case: three honest unlit rows, never an optimistic one.
    expect(starterTasks(NOTHING).every((t) => !t.ready)).toBe(true);
  });

  it('offers exactly three, in a fixed order, whatever is ready', () => {
    const order = (c: Capabilities) => starterTasks(c).map((t) => t.needs);
    expect(order(NOTHING)).toHaveLength(3);
    // A list that reshuffles as folders are indexed teaches nobody where
    // anything is.
    expect(order(EVERYTHING)).toEqual(order(NOTHING));
  });

  it('gives every task an outcome and a way to configure it', () => {
    for (const task of starterTasks(NOTHING)) {
      expect(task.outcome.length).toBeGreaterThan(0);
      // The sub-line is what you get, never the feature's name.
      expect(task.outcome.toLowerCase()).not.toMatch(/generation|feature|capability/);
      expect(task.configure.label.length).toBeGreaterThan(0);
      expect(['knowledge', 'settings']).toContain(task.configure.node);
    }
  });
});

describe('fillTo', () => {
  it('keeps the list at three, grounded prompts first', () => {
    expect(fillTo(0)).toBe(3);
    expect(fillTo(1)).toBe(2);
    expect(fillTo(2)).toBe(1);
  });

  it('shows no starters once there are three grounded prompts', () => {
    // The intended end state: a screen that stops explaining itself once it
    // has something better to say.
    expect(fillTo(3)).toBe(0);
    expect(fillTo(5)).toBe(0);
  });
});
