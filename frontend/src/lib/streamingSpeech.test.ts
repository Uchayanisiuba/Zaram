/**
 * Speech keeps pace with the text, and does not get ahead of it.
 *
 * The reply used to be spoken only once it had finished generating: `speak()`
 * was called after the token stream closed, so the user watched a long answer
 * appear in silence and then heard it read back. Sentence chunking had already
 * stopped time-to-first-sound scaling with *synthesis*; this is the other half,
 * where it stops scaling with *generation*.
 *
 * The whole correctness question is which pieces are safe to hand over before
 * the text has stopped changing, and the answer is not "every completed
 * sentence" — `splitIntoUtterances` merges a short sentence into the next one,
 * so a sentence that looks finished can still grow. Emitting it early produces
 * a pause in the wrong place, which a listener hears as a fault rather than as
 * latency, and is worse than the delay it was trying to avoid.
 */
import { describe, it, expect } from 'vitest'

import { takeCompleteUtterances } from './utterances'
import { stripCitationMarkers } from './markers'
import { speakableText } from './speakable'

/** Feed a reply through the way the token stream does: a character at a time,
 *  handing over everything so far, exactly as `pushSpeech` is called. */
function speakAsItArrives(reply: string): { spoken: string[]; atChar: number[] } {
  const spoken: string[] = []
  const atChar: number[] = []
  let consumed = 0

  for (let i = 1; i <= reply.length; i++) {
    const soFar = reply.slice(0, i)
    if (soFar.length <= consumed) continue
    const { ready, rest } = takeCompleteUtterances(soFar.slice(consumed))
    consumed = soFar.length - rest.length
    for (const piece of ready) {
      spoken.push(piece)
      atChar.push(i)
    }
  }

  const { ready } = takeCompleteUtterances(reply.slice(consumed), true)
  spoken.push(...ready)
  atChar.push(...ready.map(() => reply.length))

  return { spoken, atChar }
}

const REPLY =
  'Your day rate for Harbour is six hundred pounds. ' +
  'The last invoice went out on the third of April and it has not been paid. ' +
  'Their terms are net thirty, so it fell due on the third of May.'

describe('speaking a reply while it is still being written', () => {
  it('starts before the reply has finished arriving', () => {
    const { atChar } = speakAsItArrives(REPLY)

    // The property that matters: something is said well before the last
    // character exists. Without this the user hears nothing until generation
    // completes, which on a long answer is most of the wait.
    expect(atChar[0]).toBeLessThan(REPLY.length)
    expect(atChar[0]).toBeLessThan(REPLY.length * 0.6)
  })

  it('says the whole reply, in order, and nothing twice', () => {
    const { spoken } = speakAsItArrives(REPLY)

    // Every word reaches the synthesiser exactly once. A cursor that
    // double-counted would repeat a sentence; one that over-counted would drop
    // one, and a dropped sentence is silent — nothing would report it.
    const joined = spoken.join(' ').replace(/\s+/g, ' ').trim()
    const expected = REPLY.replace(/\s+/g, ' ').trim()
    expect(joined).toBe(expected)
  })

  it('never hands over a sentence that could still grow', () => {
    // "Hi." is under the merge threshold, so `splitIntoUtterances` would fold
    // it into whatever follows. Handing it over the moment its full stop
    // arrives would speak it alone and put a pause where the text has none.
    const { ready, rest } = takeCompleteUtterances('Hi.')

    expect(ready).toEqual([])
    expect(rest).toBe('Hi.')
  })

  it('says a short reply once the stream ends, rather than swallowing it', () => {
    // The other half of the rule above: held back while more might arrive,
    // released when nothing will.
    const { ready } = takeCompleteUtterances('Hi.', true)

    expect(ready).toEqual(['Hi.'])
  })

  it('keeps the space between a held fragment and the tokens that follow', () => {
    // `splitIntoUtterances` trims, so a remainder taken from its output rather
    // than sliced from the source would lose the trailing space and run the
    // next token into the last word.
    const { rest } = takeCompleteUtterances('That is settled. And then ')

    expect(rest.endsWith(' ')).toBe(true)
    expect(`${rest}we`).toContain('then we')
  })

  it('does not split a figure across two utterances', () => {
    // Already guarded in the splitter; asserted here because the streaming path
    // calls it on every token, which is many more chances to split mid-number.
    const { spoken } = speakAsItArrives(
      'The total is £1,470.50 including VAT. Payment is due on receipt of this note.',
    )

    expect(spoken.join(' ')).toContain('£1,470.50')
  })
})

describe('what reaches the synthesiser', () => {
  it('carries no citation markers', () => {
    // The defect this was written from: `ChatSurface` and `SpeakButton` both
    // stripped them, and the automatic speech path did not — so Kokoro was
    // asked to pronounce "[M1]" in the middle of a sentence. Nothing failed,
    // because nothing asserts what a synthesiser is told to say.
    const raw = 'Your rate is six hundred pounds [M1]. It has not been paid [M2].'
    const { spoken } = speakAsItArrives(stripCitationMarkers(raw))

    expect(spoken.join(' ')).not.toMatch(/\[[MS]\d+\]/)
    expect(spoken.join(' ')).toContain('six hundred pounds')
  })

  it('strips a marker split across tokens, which per-token filtering cannot', () => {
    // `[M1]` streams as `[M` then `1]`. A filter applied to each token sees
    // neither, which is why stripping happens on accumulated text.
    expect(stripCitationMarkers('paid' + ' [M' + '1]' + '.')).toBe('paid.')
  })
})

describe('a code block is stepped over, not read', () => {
  /**
   * The whole pipeline `pushSpeech` runs: clean the accumulated reply, then
   * take whatever utterances are now complete, advancing a character cursor
   * that never looks back.
   *
   * **The two halves are tested apart and were never tested together.**
   * `speakable.test.ts` proves the cleaned form of a prefix is a prefix of the
   * cleaned form of the whole, and the harness above proves the cursor says
   * everything once and in order — but it feeds on the raw reply, so nothing
   * asserted that a code block stays out of the audio *while streaming*. That
   * is the combination a listener actually gets.
   */
  const speakCleaned = (reply: string): string[] => {
    const spoken: string[] = []
    let consumed = 0
    let cleaned = ''

    for (let i = 1; i <= reply.length; i++) {
      cleaned = speakableText(reply.slice(0, i))
      if (cleaned.length <= consumed) continue
      const { ready, rest } = takeCompleteUtterances(cleaned.slice(consumed))
      consumed = cleaned.length - rest.length
      spoken.push(...ready)
    }
    const { ready } = takeCompleteUtterances(cleaned.slice(consumed), true)
    spoken.push(...ready)
    return spoken
  }

  const REPLY_WITH_CODE =
    'Here is the function that does it.\n\n' +
    '```python\n' +
    'def total(rows):\n' +
    '    return sum(r.amount for r in rows)\n' +
    '```\n\n' +
    'Run it against the April invoices.'

  it('says the prose on both sides and none of the code', () => {
    const said = speakCleaned(REPLY_WITH_CODE).join(' ')

    expect(said).toContain('Here is the function that does it.')
    // The point of the request: the block is stepped over and the next block
    // of prose is reached, rather than the reply ending at the code.
    expect(said).toContain('Run it against the April invoices.')

    for (const fragment of ['def total', 'return sum', 'r.amount', 'python', '```']) {
      expect(said, `"${fragment}" reached the synthesiser`).not.toContain(fragment)
    }
  })

  it('speaks the opening sentence before the block has closed', () => {
    // Waiting for the fence to close would make the silence scale with how much
    // code there is, which is the failure streaming speech exists to avoid.
    const upToTheFence = REPLY_WITH_CODE.slice(0, REPLY_WITH_CODE.indexOf('def total'))
    expect(speakCleaned(upToTheFence).join(' ')).toContain('Here is the function that does it.')
  })

  it('says nothing twice when the block closes', () => {
    // The cursor advances over cleaned text. If closing the fence changed
    // anything behind it, the sentence before the block would be replayed.
    const said = speakCleaned(REPLY_WITH_CODE)
    const first = said.filter((piece) => piece.includes('Here is the function'))
    expect(first.length).toBe(1)
  })
})
