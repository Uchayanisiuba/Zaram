/**
 * Type a model name, because a dropdown cannot hold OpenRouter's catalogue.
 *
 * The last piece of the model picker, and the smallest of its three
 * conditions — the hard one shipped first. `_unplaceable_model_refusal` in
 * `main.py` already refuses a name the catalogue cannot place *before*
 * dispatch, so a typed string can no longer fall through to Ollama and come
 * back as `model 'anthropic/claude-sonnet-4.5' not found` from a server the
 * user never mentioned. What is left is the field itself and the sentence
 * beside it.
 *
 * Behind **Advanced**, per `CLAUDE.md`'s three tiers of control: default,
 * preference, then per-task assignment, "so a non-technical user never sees
 * the third". A `<details>` rather than a state flag because the browser
 * already knows how to expand a disclosure and announce it.
 *
 * Three rules, and each is one a friendlier version of this field would break.
 *
 * **It says what the terms are while the user is choosing.** Same rule as
 * `CloudKeyForm`, which shows the catalogue's note under the picker rather
 * than behind a disclosure. A name typed here can be a `:free` model whose
 * prompts are logged and trained on, and that is the one fact worth having
 * before the choice rather than after it.
 *
 * **`selectableByDefault` is not this field's business.** It stops *Zaram*
 * routing to a provider whose terms are unknown; it must never stop a person
 * choosing one knowingly. That is the line between a consent gate and a
 * paternalism gate, and this field is on the user's side of it.
 *
 * **A typed name widens nothing.** Nothing supplied from outside may enlarge
 * what is permitted — the same rule that governs a tool description. Naming a
 * cloud model does not connect its provider, does not create a host rule, and
 * does not permit an egress; the field says so rather than letting a saved
 * name imply consent that was never given.
 *
 * **And it never says a name is wrong on the strength of not having looked.**
 * The backend refusal resolves every uncertainty to *no refusal* — no provider
 * layer, a discovery that has not run, an empty catalogue — because a guard
 * built on our own missing bookkeeping fires hardest on the first message
 * after a boot. This mirrors that: with no discovery, the field reports that
 * it cannot say, which is a different sentence from "that model does not
 * exist".
 */
import { useState } from 'react';

import type { DiscoveredModel } from '@/services/settingsClient';

interface AdvancedModelFieldProps {
  /** What discovery found, or `null` when it has not been run in this session.
   *
   *  `null` is not an empty list. One means "nothing to compare against yet"
   *  and the other means "compared, and it is not there" — collapsing them is
   *  how this field would come to call a real model imaginary. */
  models: DiscoveredModel[] | null;
  /** The model currently chosen, or null for "Zaram decides". */
  chosen: string | null;
  /** Persist a typed name. `''` hands the choice back to Zaram. */
  onChoose: (model: string) => void | Promise<void>;
  busy?: boolean;
}

/** What happens to a prompt sent to this model, in a sentence.
 *
 *  The strings are the backend's `DataPolicy` members, and `null` is the
 *  absence of an answer rather than a fourth kind of answer — `DataPolicy`'s
 *  own docstring is explicit that an unknown policy is not a member, because
 *  "an enum member would eventually get a label in a picker and start looking
 *  like a choice". So the unknown case describes the gap; it does not
 *  reassure.
 */
export function describeDataPolicy(policy: string | null): string {
  switch (policy) {
    case 'never_leaves_device':
      return 'Runs on this machine. Nothing is sent.';
    case 'your_key_no_training':
      return 'Your own key, and the provider’s terms exclude training on API data. ' +
        'The prompt still leaves this device, and Activity records what went.';
    case 'logged_and_trained_on':
      return 'The provider logs prompts and may train on them. Zaram will tell you ' +
        'every time one goes.';
    default:
      return 'Terms unknown. Zaram will not route here on its own — choosing it ' +
        'is your decision, and Activity records what went.';
  }
}

/** The model a typed name refers to, matched the way the chat path matches.
 *
 *  On `id` and on `displayName`, because `_unplaceable_model_refusal` accepts
 *  either and being right about only one spelling is the defect it guards
 *  against. Trimmed, because a pasted name carries whitespace; not
 *  case-folded, because a model id is not case-insensitive and pretending
 *  otherwise would resolve to a model the backend then refuses.
 */
export function findTypedModel(
  models: DiscoveredModel[] | null,
  typed: string,
): DiscoveredModel | null {
  const name = typed.trim();
  if (!name || models === null) return null;
  return models.find((m) => m.id === name || m.displayName === name) ?? null;
}

export default function AdvancedModelField({
  models,
  chosen,
  onChoose,
  busy = false,
}: AdvancedModelFieldProps) {
  const [typed, setTyped] = useState('');
  const match = findTypedModel(models, typed);
  const name = typed.trim();
  // Only once discovery has run and found something. See the module docstring:
  // an empty shelf is not evidence about the user's machine.
  const unplaceable = name !== '' && models !== null && models.length > 0 && match === null;

  return (
    <details className="mt-1" data-testid="advanced-model">
      <summary
        className="text-[11px] cursor-pointer select-none"
        style={{ color: 'var(--color-text-muted)' }}
      >
        Advanced
      </summary>

      <div className="flex flex-col gap-2 mt-2">
        <p className="text-[11px] leading-snug" style={{ color: 'var(--color-text-muted)', maxWidth: '52ch' }}>
          Type a model name if it is not in the list above. Some providers offer
          more models than a list can hold.
        </p>

        <div className="flex items-center gap-2 flex-wrap">
          <input
            aria-label="Type a model name"
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            placeholder={chosen ?? 'provider/model-name'}
            autoComplete="off"
            spellCheck={false}
            className="px-2 py-1.5 rounded-lg text-xs flex-1 min-w-[16rem]"
            style={{
              background: 'transparent',
              border: '1px solid var(--color-border-subtle)',
              color: 'var(--color-text)',
              fontFamily: 'var(--font-mono)',
            }}
          />
          <button
            type="button"
            disabled={busy || name === ''}
            onClick={() => void onChoose(name)}
            className="px-2.5 py-1.5 rounded-lg text-[11px]"
            style={{
              border: '1px solid var(--color-border-subtle)',
              color: 'var(--color-text)',
              background: 'transparent',
              opacity: busy || name === '' ? 0.45 : 1,
              cursor: busy || name === '' ? 'default' : 'pointer',
            }}
          >
            Use this model
          </button>
        </div>

        {/* Under the field, before the button is worth pressing: the terms of
            the thing being chosen. Shown for a name that resolves, because
            that is when there is something true to say. */}
        {match && (
          <p
            className="text-[11px] leading-snug"
            style={{ color: 'var(--color-text-muted)', maxWidth: '52ch' }}
            data-testid="advanced-model-policy"
          >
            {match.displayName} · {describeDataPolicy(match.dataPolicy)}
          </p>
        )}

        {/* The name Zaram cannot place. Stated as what will happen rather than
            as a verdict, and it is the truth: the request is refused before
            dispatch, so nothing is sent to a server guessed from the name. */}
        {unplaceable && (
          <p
            className="text-[11px] leading-snug"
            style={{ color: 'var(--color-amber)', maxWidth: '52ch' }}
            data-testid="advanced-model-unplaceable"
          >
            Zaram cannot place “{name}”. You can still choose it — but until
            the provider it belongs to is connected, Zaram will refuse to send
            rather than guess where it lives.
          </p>
        )}

        {/* Discovery has not run. Not the same sentence as the one above, and
            deliberately so. */}
        {name !== '' && models === null && (
          <p
            className="text-[11px] leading-snug"
            style={{ color: 'var(--color-text-muted)', maxWidth: '52ch' }}
            data-testid="advanced-model-unlooked"
          >
            Zaram has not looked for models yet, so it cannot say whether this
            name exists or what its terms are. Use “Look for models” above
            first.
          </p>
        )}

        <p className="text-[11px] leading-snug" style={{ color: 'var(--color-text-faint)', maxWidth: '52ch' }}>
          Naming a model here permits nothing. A cloud model still needs its
          provider connected and its destination allowed, and every request is
          recorded in Activity.
        </p>
      </div>
    </details>
  );
}
