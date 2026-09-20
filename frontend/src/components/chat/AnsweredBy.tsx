/**
 * Which model answered, and where it ran — on every reply.
 *
 * `CLAUDE.md` has required this since routing existed: *"Every reply names the
 * model that answered and why"*, and *"Never hide the model"*. Nothing did.
 * The cost was concrete rather than theoretical: the maintainer connected a
 * cloud provider, asked questions, and had no way to tell whether anything ever
 * reached it — *"I don't think Zaram is connected to the cloud even though I'm
 * logged in with OpenRouter, nothing indicates it's gotten a response from a
 * cloud LLM."* Every layer below was working; the answer simply never said.
 *
 * **It is not decoration and it is not a badge.** Locality is the one claim in
 * this interface a user checks before trusting the rest, so it is stated in
 * words — "on this machine" / "left this device" — rather than as a colour a
 * user has to learn. `OrbStatusLabel` makes the same argument for the same
 * reason, and the embodiment rule refuses a rim colour standing in for a
 * sentence.
 *
 * **Null locality renders no locality.** The backend answers `null` for a model
 * it could not place, and that travels intact to here. Saying "on this machine"
 * about an unresolved model would be a confident false claim on exactly the
 * field that must never be guessed — the same three-valued discipline
 * `vram_bytes` keeps by returning `None` rather than `0`.
 *
 * **Why, honestly.** `chosenBy` says where the choice came from — this message,
 * Settings, the question itself, or Zaram's usual pick. `CLAUDE.md`'s example
 * phrasing is "routed to qwen2.5-coder — coding task"; the backend now sends
 * `task` when the message was classified against the intent exemplars and the
 * intent asked for a model specialisation that is installed. It stays a label
 * for *that* decision only — an ordinary message still reads "Zaram's pick",
 * because claiming every reply was routed would be the invented value this
 * note was originally written to forbid.
 */
import { useState } from 'react';

import { describeDataPolicy } from '@/components/settings/AdvancedModelField';
import { fetchModels, type DiscoveredModel } from '@/services/settingsClient';
import type { ChatAttribution } from '@/stores/chatStore';
import type { ChatTiming } from '@/services/chatClient';

/** "first word in 3.9 s" — the one number a person feels, on the line that
 *  already explains the reply. The rest of the breakdown rides the tooltip.
 *
 *  **Measured or absent.** A phase the backend did not time is null and is
 *  left out, never printed as 0 s: a zero here would read as instant, which
 *  is the opposite of unmeasured. The instrument behind "Zaram is slow
 *  sometimes" — `docs/PLAN.md` A1. */
export function timingLine(timing: ChatTiming | null | undefined): { text: string; title: string } | null {
  if (!timing) return null;
  const s = (ms: number | null) =>
    ms === null ? null : ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)} s`;
  // What the person waited: everything before the model's first word,
  // measured from the question. The engine's phases are disjoint — recall,
  // plan, the steps that ran before the answer, then the prefill — so the
  // wait is their sum, and the prefill alone is one line of the breakdown.
  // Seen 20 September 2026: "first word in 0 ms" under a six-second wait.
  const waited =
    timing.firstTokenMs === null
      ? null
      : (timing.recallMs ?? 0) + (timing.planMs ?? 0) + (timing.stepsMs ?? 0) + timing.firstTokenMs;
  const first = s(waited);
  const total = s(timing.totalMs);
  if (!first && !total) return null;
  const parts = [
    ['recall', s(timing.recallMs)],
    ['plan', s(timing.planMs)],
    ['steps', s(timing.stepsMs)],
    ['prefill', s(timing.firstTokenMs)],
    ['writing', s(timing.generationMs)],
    ['tools', s(timing.toolsMs ?? null)],
    ['more rounds', s(timing.roundsMs ?? null)],
    ['total', total],
  ].filter(([, v]) => v !== null) as [string, string][];
  return {
    text: first ? `first word in ${first}` : `${total} in all`,
    title: parts.map(([k, v]) => `${k} ${v}`).join(' · '),
  };
}

/** Where the choice came from, in words a person would use. Unknown values
 *  render nothing rather than being echoed raw — a backend that grows a fourth
 *  value must not leak an identifier onto the screen. */
const CHOSEN_BY: Record<string, string> = {
  request: 'asked for on this message',
  // The user's standing answer for *this kind* of question, set under
  // Advanced. Distinct from `task` on purpose: that one is Zaram's own match,
  // and crediting the product with a choice the person made would be a false
  // claim on the one line whose job is to say who chose.
  assignment: 'your model for this kind of question',
  settings: 'your choice in Settings',
  task: 'matched to this question',
  zaram: "Zaram's pick",
};

/** The locality sentence. Absent for an unresolved model — see the note above. */
const LOCALITY: Record<string, string> = {
  local: 'on this machine',
  cloud: 'left this device',
};

export function AnsweredBy({
  attribution,
  /** Re-ask this question of a different model.
   *
   *  **Why the switch lives here and not in the composer.** A picker beside
   *  the input asks someone to predict, before typing, which model will answer
   *  best — which rule 7e says never to ask, because it is decidable from
   *  behaviour and the router already decides it. This is the same choice
   *  offered at the moment of doubt instead: after a reply exists and can be
   *  judged. Rule 7h, in its own words — "offer at the moment of doubt; never
   *  make the user choose in advance".
   *
   *  It is also the only place a model name is not out of place. `CLAUDE.md`
   *  bans filenames from the primary path and simultaneously requires "never
   *  hide the model", so this line already names one; offering its
   *  alternatives beside it adds no vocabulary the reader has not just been
   *  shown.
   *
   *  `MessageActions` argues that re-asking belongs on the user's own message,
   *  "putting the control on the reply would imply the reply is what gets
   *  regenerated". That still holds for a plain retry and it is why this is
   *  worded as asking another *model* rather than as regenerating: the
   *  question is re-sent, and the difference is which model receives it.
   *
   *  Optional, so every existing caller and every test rendering this on its
   *  own is unchanged. */
  onAskAnother,
  timing,
}: {
  attribution: ChatAttribution | null | undefined;
  onAskAnother?: (model: string) => void;
  /** Where the time went, when the backend measured it. */
  timing?: ChatTiming | null;
}) {
  const took = timingLine(timing);
  const [open, setOpen] = useState(false);
  const [models, setModels] = useState<DiscoveredModel[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);

  /** Fetched on the press, never on render.
   *
   *  `fetchModels` asks every connected cloud provider what it offers, so it
   *  is a network call that goes through the egress gate — `settingsClient`
   *  says outright that this is why the interface asks for it "on a button
   *  rather than on mount". A reply is rendered every time a conversation is
   *  reopened; discovery must not ride along with it. */
  async function reveal() {
    setOpen(true);
    if (models || loading) return;
    setLoading(true);
    setFailed(false);
    try {
      setModels(await fetchModels());
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }

  if (!attribution?.model) return null;

  const locality = attribution.locality ? LOCALITY[attribution.locality] : null;
  const why = attribution.chosenBy ? CHOSEN_BY[attribution.chosenBy] : null;
  // The provider is worth naming only when the request actually went somewhere.
  // "via ollama" beside "on this machine" is noise; "via openrouter" beside
  // "left this device" is the fact the user was looking for.
  const provider =
    attribution.locality === 'cloud' && attribution.provider ? attribution.provider : null;

  // An embedder cannot hold a conversation — Ollama answers `/api/generate`
  // for `bge-m3` with a 400 — and the model that just answered is not an
  // alternative to itself.
  const alternatives = (models ?? []).filter(
    (m) => m.category === 'llm' && m.displayName !== attribution.model,
  );

  return (
    <div className="mt-1">
      <p
        data-testid="answered-by"
        className="trace leading-snug"
        title={why ? `Model: ${why}` : undefined}
      >
        {/* The site's trace roles, on the line the site is describing:
            the model in the text tone, "on this machine" in ok, and a
            request that left in violet — the cloud colour, and only there. */}
        <span style={{ color: 'var(--color-text)' }}>{attribution.model}</span>
        {provider ? <span className="role-vi">{` · via ${provider}`}</span> : null}
        {locality ? (
          <span className={attribution.locality === 'cloud' ? 'role-vi' : 'role-ok'}>{` · ${locality}`}</span>
        ) : null}
        {why ? <span className="role-dim">{` · ${why}`}</span> : null}
        {took ? (
          <span className="role-dim" title={took.title} data-testid="took">{` · ${took.text}`}</span>
        ) : null}
        {onAskAnother && !open && (
          <>
            {' · '}
            <button
              type="button"
              onClick={() => void reveal()}
              data-testid="ask-another"
              className="underline underline-offset-2 hover:text-slate-300 transition-colors"
              style={{ color: '#64748b' }}
            >
              ask another
            </button>
          </>
        )}
      </p>

      {onAskAnother && open && (
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          {loading && <span className="text-xs text-slate-500">Looking…</span>}
          {failed && (
            // Named rather than silent, and it says where the failure was: a
            // provider that could not be reached is a different problem from
            // having no other model.
            <span className="text-xs text-slate-500">
              Could not reach the model list.
            </span>
          )}
          {!loading && !failed && alternatives.length === 0 && (
            <span className="text-xs text-slate-500">
              No other model is available. Connect one in Settings.
            </span>
          )}
          {alternatives.map((model) => (
            <button
              key={model.id}
              type="button"
              onClick={() => {
                setOpen(false);
                // `displayName` rather than `id`: the backend accepts either,
                // and its own note says display name "is what this path
                // speaks".
                onAskAnother(model.displayName);
              }}
              // The data policy on the button, not behind it. `CLAUDE.md`:
              // naming the deal is a primary feature, not a detail — and this
              // is the moment a person is choosing to send a question
              // somewhere new.
              title={`${model.locality === 'cloud' ? 'Leaves this device' : 'On this machine'} · ${describeDataPolicy(model.dataPolicy)}`}
              className="px-1.5 py-0.5 rounded-full border text-xs leading-none transition-colors hover:bg-white/5"
              style={{
                borderColor:
                  model.locality === 'cloud'
                    ? 'rgba(217,164,65,0.45)'
                    : 'rgba(100,116,139,0.45)',
                color: model.locality === 'cloud' ? 'var(--color-amber, #d9a441)' : '#94a3b8',
              }}
            >
              {model.displayName}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="text-xs text-slate-600 hover:text-slate-400 transition-colors"
          >
            cancel
          </button>
        </div>
      )}
    </div>
  );
}
