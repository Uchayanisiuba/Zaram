import type { DiscoveredModel } from '@/services/settingsClient';

/**
 * Whether *Auto* has a choice to make, and what to say when it does not.
 *
 * Asked for on 7 September 2026: activate the Auto control when more than one
 * model is available to route between. Until now all three modes were always
 * live, and on a machine with one chat model that is a control that cannot
 * change anything — press any of the three and the same model answers, because
 * there is nothing else for it to answer instead. `CLAUDE.md` is direct about
 * that shape: *"a status indicator over hardcoded data is worse than no
 * indicator"*, and a preference that is inert is the same failure wearing a
 * button.
 *
 * **What makes Auto meaningful is how many models it may choose between, not
 * how many are resident.** Those are two different questions and merging them
 * is the mistake to avoid here. Residency decides *which* candidate wins — the
 * 6 September routing change prefers a model already loaded over one that
 * merely fits, because a swap costs 90–180 seconds on this hardware. But a
 * model that is installed and unloaded is still a model Auto can route to; it
 * just costs a load. Gating the control on residency would switch Auto off
 * every time the card went quiet, which is most of the time.
 *
 * **`selectable_by_default` is respected, and it is why cloud usually does not
 * count.** It stops Zaram sending work to a free tier that trains on it
 * without being asked, so a connected-but-not-selectable cloud model is not a
 * candidate Auto may reach on its own. The user can still pick it by name from
 * the list below the modes — that is a different act, and the reason the list
 * shows every installed model regardless.
 *
 * **The saved preference is never rewritten to match this.** A first version
 * had a `displayedPreference` that showed `prefer_local` when Auto could not be
 * offered; it was removed before it shipped, for two reasons. It had no caller,
 * which is this repository's most-repeated defect. And it was wrong on its own
 * terms: Auto with one candidate is not broken, it is Auto correctly picking
 * the only model there is, and reporting a setting the user did not choose is a
 * worse lie than a mode button that is dim. The chip states what is saved; the
 * tooltip states why the option cannot currently change anything.
 */
export interface AutoAvailability {
  /** Whether Auto can route between more than one candidate. */
  usable: boolean;
  /** How many candidates it may choose between without being asked. */
  candidates: number;
  /** Why not, for the control's tooltip. Empty when it is usable. */
  reason: string;
}

/**
 * @param models Every discovered model, as the picker receives them.
 * @param cloudPermitted Whether anything may leave the device at all. A cloud
 *   candidate that cannot be reached is not a candidate, and counting it would
 *   light up Auto on a machine where it still has one option.
 */
export function autoAvailability(
  models: readonly DiscoveredModel[] | null | undefined,
  cloudPermitted: boolean,
): AutoAvailability {
  const chats = (models ?? []).filter((m) => m.category === 'llm');

  // What Zaram may reach on its own: a chat model it is permitted to pick, and
  // for a cloud one, a device that is permitted to send.
  const candidates = chats.filter(
    (m) => m.selectableByDefault && (m.locality === 'local' || cloudPermitted),
  ).length;

  if (candidates >= 2) return { usable: true, candidates, reason: '' };

  // Named separately, because they are different problems with different
  // fixes — the same reason the cloud tooltip already distinguishes "no
  // provider connected" from "nothing may leave yet".
  if (chats.length === 0) {
    return { usable: false, candidates, reason: 'No chat model is installed yet' };
  }
  if (candidates === 0) {
    return {
      usable: false,
      candidates,
      reason:
        'No model Zaram may pick on its own — choose one below, or allow one in Settings',
    };
  }
  return {
    usable: false,
    candidates,
    reason: 'Only one model to route to, so Auto would always pick it',
  };
}
