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
import type { ChatAttribution } from '@/stores/chatStore';

/** Where the choice came from, in words a person would use. Unknown values
 *  render nothing rather than being echoed raw — a backend that grows a fourth
 *  value must not leak an identifier onto the screen. */
const CHOSEN_BY: Record<string, string> = {
  request: 'asked for on this message',
  settings: 'your choice in Settings',
  task: 'matched to this question',
  zaram: "Zaram's pick",
};

/** The locality sentence. Absent for an unresolved model — see the note above. */
const LOCALITY: Record<string, string> = {
  local: 'on this machine',
  cloud: 'left this device',
};

export function AnsweredBy({ attribution }: { attribution: ChatAttribution | null | undefined }) {
  if (!attribution?.model) return null;

  const locality = attribution.locality ? LOCALITY[attribution.locality] : null;
  const why = attribution.chosenBy ? CHOSEN_BY[attribution.chosenBy] : null;
  // The provider is worth naming only when the request actually went somewhere.
  // "via ollama" beside "on this machine" is noise; "via openrouter" beside
  // "left this device" is the fact the user was looking for.
  const provider =
    attribution.locality === 'cloud' && attribution.provider ? attribution.provider : null;

  const parts = [attribution.model, provider ? `via ${provider}` : null, locality].filter(Boolean);

  return (
    <p
      data-testid="answered-by"
      className="mt-1 text-[10px] leading-snug"
      style={{ color: attribution.locality === 'cloud' ? 'var(--color-amber, #d9a441)' : '#64748b' }}
      title={why ? `Model: ${why}` : undefined}
    >
      {parts.join(' · ')}
      {why ? <span style={{ color: '#64748b' }}>{` · ${why}`}</span> : null}
    </p>
  );
}
