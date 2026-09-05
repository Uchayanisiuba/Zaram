/**
 * Citation markers are grounding, not language.
 *
 * The engine emits `[M1]` and `[S2]` inline so a claim can be traced back to
 * the fact or source that produced it. They mean nothing to the reader and they
 * must never reach one — and there are now three callers that need them gone,
 * which is why this stopped being a private helper in `ChatSurface`.
 *
 * **The third caller was missed and it was the one that mattered.** The chat
 * transcript stripped them and the speak-aloud button stripped them, but the
 * path that speaks a reply automatically did not — so Kokoro was handed the raw
 * text and pronounced the markers aloud, mid-sentence. Silent in every test,
 * because nothing asserts what a synthesiser is asked to say.
 *
 * Applied to accumulated text rather than to individual tokens: a marker
 * usually arrives split across several tokens as it streams, so a per-token
 * filter sees `[M` and `1]` and matches neither.
 */

/** `[M1]`, `[S12]`, with any leading whitespace they were sitting behind. */
const MARKER = /\s*\[[MS]\d+\]/g

export function stripCitationMarkers(text: string): string {
  return (text ?? '').replace(MARKER, '')
}
