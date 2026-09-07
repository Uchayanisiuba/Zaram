/**
 * The third tier of control — a model per kind of request — in the words the
 * screen uses and the eligibility the picker enforces.
 *
 * `CLAUDE.md` names three tiers: Zaram decides, then *Prefer local · Auto ·
 * Prefer cloud*, then per-task assignment behind Advanced. This module is the
 * copy and the rules for the third, kept out of `SettingsWorkspace` so both
 * can be asserted without mounting a screen that fetches five endpoints.
 *
 * **The slots are the backend's, not this file's.** `task_slots` on
 * `/routing/preference` is the authority, because a slot is real only if
 * `_resolve_model` consults it. A row invented here would be a control the
 * user could set that then governed nothing — the *never render invented
 * values* rule, applied to a control rather than to a readout, where it is
 * worse: a wrong readout misinforms, a wrong control lets someone believe they
 * have configured their machine. So a slot with no copy renders no row, and a
 * slot the backend stops routing on disappears without this file changing.
 */
import type { DiscoveredModel } from '@/services/settingsClient';

export interface TaskSlotCopy {
  /** The row's label. A kind of question, in the user's words. */
  label: string;
  /** What the value reads as when nothing is assigned. Not "none" — an
   *  unassigned slot is not "no model", it is the general choice standing. */
  unassigned: string;
  /** Why this row exists and what setting it actually does. */
  detail: string;
}

export const TASK_SLOT_COPY: Record<string, TaskSlotCopy> = {
  code: {
    label: 'Coding questions',
    unassigned: 'whichever model answers',
    detail:
      'Sends questions Zaram reads as being about code to this model, and leaves everything else ' +
      'alone. A model built for code is usually better at it — but a general model is a real ' +
      'answer, so every model is offered here and the specialists are marked.',
  },
  vision: {
    label: 'Questions about pictures',
    unassigned: 'whichever model can see',
    detail:
      'Only models that can accept an image are offered. That is not a ranking — a model that ' +
      'cannot see is not a worse answer about a screenshot, it is not an answer — so the choice ' +
      'is not offered rather than being offered and warned about.',
  },
};

/**
 * The models that may be assigned to `slot`.
 *
 * **Two different jobs, and only one of them is filtering.** A *capability* is
 * a precondition and removes a model from the list; a *specialisation* is a
 * preference and only marks one. Merging the two is the error `CLAUDE.md`
 * records as this codebase's most expensive recurring bug, and in this
 * direction it would quietly hide every general model from the coding slot on
 * a machine that has no coding model — leaving a picker with nothing in it and
 * no way to tell that from "nothing installed".
 *
 * An unknown slot returns nothing, so a backend that grows a third slot before
 * this file has copy for it renders no row rather than an untitled one with a
 * picker under it.
 */
export function eligibleForSlot(models: DiscoveredModel[], slot: string): DiscoveredModel[] {
  if (!(slot in TASK_SLOT_COPY)) return [];
  // An embedder cannot hold a conversation — Ollama answers `/api/generate`
  // for `bge-m3` with a 400 — so it is excluded from every slot for the same
  // reason it is excluded from *Which model answers*.
  const usable = models.filter((m) => m.category !== 'embedding');
  if (slot === 'vision') return usable.filter((m) => m.supportsVision);
  return usable;
}

/**
 * The name to show for an assigned model, given what discovery found.
 *
 * The stored value is whatever the picker sent or a person typed — a catalogue
 * id, or a display name. Showing the raw id would put `ollama:qwen2.5-coder:14b`
 * on screen, a string that appears nowhere else in the interface, prefixed by a
 * word that looks like part of the model's name. That exact complaint is why
 * `_current_inference` resolves a display name before the identity block sees
 * it.
 *
 * A stored name the catalogue cannot place is returned **unchanged**, never
 * blanked: the user typed it, it is what will be sent, and the backend refuses
 * it by name at dispatch. Hiding it here would leave them looking at an empty
 * row wondering what they set.
 */
export function displayAssigned(models: DiscoveredModel[] | null, stored: string): string {
  if (!models) return stored;
  const found = models.find((m) => m.id === stored || m.displayName === stored);
  return found ? found.displayName : stored;
}
