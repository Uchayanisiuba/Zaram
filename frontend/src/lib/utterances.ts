/**
 * Splitting a reply into the units speech is synthesised in.
 *
 * **This is the whole latency fix.** Kokoro on CPU runs at roughly real time:
 * measured on 10 August 2026, "Hi." produced 1.25s of audio in 3.4s of wall
 * clock, and a 30-word passage took 8.2s. Synthesising a whole reply before
 * playing any of it therefore costs the user the *entire* duration of the reply
 * before they hear the first word — which is what "huge delay" is. Nothing was
 * streaming; `speechStore` made one blocking request for the lot.
 *
 * Split into sentences and the wait becomes the first sentence only, with the
 * rest synthesised while that one plays. Time-to-first-sound stops scaling with
 * reply length, which is the property that makes speech feel immediate. It does
 * not make synthesis faster — nothing here can — it stops the user waiting for
 * work whose output they will not need for another ten seconds.
 *
 * Two failure modes this guards against, both of which make it worse rather
 * than better:
 *
 * **Splitting inside a number.** "£1,470.50" broken after "1,470." is spoken as
 * two utterances with a pause in the middle, and the figure on an invoice is
 * exactly the thing that must not be garbled.
 *
 * **Chunks too small to be worth a request.** Every chunk costs a round trip
 * and a model call. A two-word fragment spends that overhead to buy a third of
 * a second of audio, so short pieces are merged forward until they are worth
 * saying on their own.
 */

/** Below this, a chunk costs more in overhead than the audio it buys. */
const MIN_CHARS = 24

/** Above this, one chunk is long enough that waiting for it is the old problem
 *  again, so a clause boundary is used even though a sentence boundary is
 *  better. Roughly ten seconds of speech. */
const MAX_CHARS = 240

/** Abbreviations whose full stop does not end a sentence. Deliberately short:
 *  a long list is a different kind of wrong, and the cost of a miss here is a
 *  slightly early pause rather than a mangled number. */
const ABBREVIATIONS = /(?:^|\s)(?:mr|mrs|ms|dr|prof|st|no|vs|etc|e\.g|i\.e|approx|inc|ltd|co)\.$/i

/** A full stop between digits is a decimal point, not a sentence end. */
const DECIMAL_POINT = /\d[.,]$/

function endsSentence(text: string, next: string): boolean {
  if (DECIMAL_POINT.test(text) && /^\d/.test(next)) return false
  if (ABBREVIATIONS.test(text)) return false
  // A single capital before the stop is an initial — "J. Smith".
  if (/(?:^|\s)[A-Z]\.$/.test(text)) return false
  return true
}

/** Break one over-long piece at clause boundaries, then at whitespace.
 *
 *  Prefers a comma or a semicolon because a pause there sounds intended. A hard
 *  break at a word boundary is the last resort and still beats a chunk that
 *  reintroduces the delay this module exists to remove. */
function breakLongPiece(piece: string): string[] {
  if (piece.length <= MAX_CHARS) return [piece]

  const out: string[] = []
  let rest = piece
  while (rest.length > MAX_CHARS) {
    const window = rest.slice(0, MAX_CHARS)
    const clause = Math.max(window.lastIndexOf(', '), window.lastIndexOf('; '))
    const cut = clause > MIN_CHARS ? clause + 1 : window.lastIndexOf(' ')
    if (cut <= 0) break
    out.push(rest.slice(0, cut).trim())
    rest = rest.slice(cut).trim()
  }
  if (rest) out.push(rest)
  return out
}

/**
 * A reply, as the pieces it should be spoken in.
 *
 * Order is preserved and nothing is dropped: joining the result reproduces the
 * input's words. A caller plays them in sequence, synthesising ahead.
 */
export function splitIntoUtterances(text: string): string[] {
  const source = (text ?? '').trim()
  if (!source) return []

  const pieces: string[] = []
  let start = 0

  for (let i = 0; i < source.length; i++) {
    const char = source[i]
    if (char !== '.' && char !== '!' && char !== '?' && char !== '\n') continue

    // Absorb trailing quotes and brackets so a closing mark travels with the
    // sentence it ends rather than opening the next one.
    let end = i + 1
    while (end < source.length && '"\'”’)]'.includes(source[end])) end++

    const candidate = source.slice(start, end)
    const following = source.slice(end).trimStart()

    const isBreak =
      char === '\n' || (/^\s|^$/.test(source.slice(end, end + 1)) && endsSentence(candidate.trimEnd(), following))

    if (!isBreak) continue

    const piece = candidate.trim()
    if (piece) pieces.push(piece)
    start = end
  }

  const tail = source.slice(start).trim()
  if (tail) pieces.push(tail)

  // Merge anything too small to be worth its own request into the next piece,
  // and the last one backwards so a trailing "Thanks." does not stand alone.
  const merged: string[] = []
  for (const piece of pieces) {
    const previous = merged[merged.length - 1]
    if (previous !== undefined && previous.length < MIN_CHARS) {
      merged[merged.length - 1] = `${previous} ${piece}`
    } else {
      merged.push(piece)
    }
  }
  if (merged.length > 1 && merged[merged.length - 1].length < MIN_CHARS) {
    const last = merged.pop() as string
    merged[merged.length - 1] = `${merged[merged.length - 1]} ${last}`
  }

  return merged.flatMap(breakLongPiece).filter(Boolean)
}

/**
 * The pieces of a still-arriving reply that are finished enough to synthesise.
 *
 * **This is what makes speech start while the text is still appearing.**
 * `splitIntoUtterances` stopped time-to-first-sound scaling with reply length,
 * but it was only ever called once the whole reply had arrived — so the user
 * still waited for the model to finish generating before hearing a word. On a
 * long answer that is most of the delay, and it is the delay that remains after
 * the synthesis fix.
 *
 * Called as tokens arrive with everything not yet handed over. Returns the
 * pieces that will not change again, and the remainder to keep and pass back in
 * with the next tokens.
 *
 * **The last piece is held back, and that is the whole subtlety.** A sentence
 * without its final full stop is not finished, and one that *has* a full stop
 * may still be merged into by `splitIntoUtterances` when the next sentence turns
 * out to be short. Emitting either produces speech that pauses in the wrong
 * place — worse than waiting, because a listener reads a wrong pause as a fault
 * rather than as latency.
 *
 * `flush` is the end of the stream: there is no more text coming, so whatever
 * is left is complete by definition and short pieces stop being worth holding.
 */
export function takeCompleteUtterances(
  pending: string,
  flush = false,
): { ready: string[]; rest: string } {
  if (flush) return { ready: splitIntoUtterances(pending), rest: '' }

  const pieces = splitIntoUtterances(pending)
  if (pieces.length === 0) return { ready: [], rest: pending }

  const last = pieces[pieces.length - 1]

  // Complete only if the text stops at a sentence boundary *and* the final
  // piece is long enough that more text would not have been merged into it.
  const endsAtBoundary = /[.!?\n]["'”’)\]]*\s*$/.test(pending)
  if (endsAtBoundary && last.length >= MIN_CHARS) {
    return { ready: pieces, rest: '' }
  }

  // Slice from the source rather than returning the split piece: splitting
  // trims, and a trimmed remainder would lose the space before the next token
  // and run two words together.
  const at = pending.lastIndexOf(last)
  return {
    ready: pieces.slice(0, -1),
    rest: at >= 0 ? pending.slice(at) : last,
  }
}
