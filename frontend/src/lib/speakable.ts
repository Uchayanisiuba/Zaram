/**
 * A reply as it should be *said*, which is not the same text as it is shown.
 *
 * Reported by the maintainer, 3 September 2026: Zaram reads code aloud, and
 * reads punctuation. Both are the same failure — the synthesiser was handed the
 * markdown the screen renders, so a fenced block became forty seconds of
 * identifiers and brackets spoken one at a time, and `**bold**` and `# Heading`
 * arrived as the symbols themselves.
 *
 * Nothing here is a rendering decision. The transcript keeps every character:
 * the code block is on screen, formatted, selectable and copyable, and this
 * governs only what goes to Kokoro.
 *
 * Three rules, and the third is the one that needed thought:
 *
 * **Code is not read.** Not summarised, not replaced with a spoken stand-in —
 * omitted. A block is unusable as speech at any length, and inventing "code
 * block" to say in its place is a claim the model did not make. The prose
 * around it still speaks, so "here is the function that does it:" is followed
 * by the next sentence, and the code is where it always was.
 *
 * **Inline code keeps its contents.** `main.py` and `--strictPort` carry the
 * meaning of the sentence they are in; only the backticks go. Dropping them
 * would leave "open and edit" with the two things being named missing.
 *
 * **The transform must be prefix-stable, because speech is streaming.**
 * `speechStore` cleans the accumulated reply on every token and keeps a
 * character cursor into the result, so a cleaned prefix that changes when more
 * text arrives would replay or skip audio. Every rule below therefore either
 * deletes characters outright or, for an unterminated fence, deletes to the end
 * of the text — a region that only ever grows forward and can never uncover
 * something already spoken.
 */

import { stripCitationMarkers } from '@/lib/markers'

/** A closed fenced block, with its language tag and both fences. */
const FENCED_BLOCK = /```[\s\S]*?```/g

/** `` `x` `` — inline code, keeping what it names.
 *
 *  The lookarounds keep it off a fence. Without them it paired the first two
 *  backticks of an opening ``` as an empty inline span, which left a single
 *  backtick where a fence had been — and the fence rules, which is what stops
 *  a code block being read aloud, no longer had a fence to recognise. */
const INLINE_CODE = /(?<!`)`([^`\n]+)`(?!`)/g

/** `![alt](url)` — an image reference. Nothing here is speech: the alt text is
 *  a description for a reader who cannot see it, and the URL is a path. */
const IMAGE = /!\[[^\]]*\]\([^)]*\)/g

/** `[text](url)` — the text is the sentence, the URL is not. */
const LINK = /\[([^\]]*)\]\([^)]*\)/g

/**
 * The end of the text, while it is still undecided.
 *
 * **This is the half that the streaming property test found, and it would not
 * have been found any other way.** Every rule above needs a construct to be
 * finished before it can tell what it is, and a reply arrives a few characters
 * at a time — so there is always a moment when a code fence looks like one
 * backtick, a link looks like `[the terms]`, and a bullet looks like a lone
 * hyphen. Cleaned as though finished, each of those puts a stray symbol into
 * the audio and then changes underneath the cursor that has already passed it.
 *
 * So an unfinished tail is not spoken until it is finished. Three shapes, all
 * anchored to the end of the text, all of which resolve within a token or two:
 *
 * - an opening fence, which swallows the rest of what has arrived, because
 *   everything after it is code until the closing fence says otherwise
 * - a backtick with no partner *on its own line* — an inline span in progress.
 *   Bounded to the line so that a stray backtick in prose costs one character
 *   rather than the rest of the reply
 * - `[`, `[text]`, or `[text](url` with no closing bracket yet
 * - a line that so far contains only the marks a line can start with
 *
 * Nothing is lost by waiting: `takeCompleteUtterances` holds the last piece
 * back regardless, because a sentence can still be merged into.
 */
const PENDING_TAIL =
  /(?:```[\s\S]*|`+[^`\n]*|!?\[[^\]]*(?:\](?:\([^)]*)?)?|(?:^|\n)[ \t]*[-*+#>=~_]+[ \t]*)$/

/** A bare URL. Read aloud it is a minute of "slash", "dot", "hyphen". */
const BARE_URL = /\bhttps?:\/\/\S+/g

/** Heading marks and blockquote arrows at the start of a line. Anchored, so
 *  the decision is made from the line's first characters and never revised. */
const LINE_PREFIX = /^[ \t]*(?:#{1,6}|>+)[ \t]*/gm

/** A bullet's marker. The item is spoken; the dash is not. */
const BULLET = /^[ \t]*[-*+][ \t]+/gm

/** Three or more of a rule character: `---`, `***`, `===`, and the dashes in a
 *  table's separator row. Matched anywhere rather than anchored to a whole
 *  line, because a line is not finished while it is streaming. */
const RULE_RUN = /[-=_*~]{3,}/g

/** What is left of markdown once structure is gone: emphasis marks, table
 *  pipes, stray backticks and brackets. Replaced with a space rather than
 *  deleted so `user_settings` says two words instead of one. */
const SYMBOLS = /[*_~`|[\]]+/g

/** Runs of whitespace, including the gaps the rules above leave behind. */
const WHITESPACE = /[ \t]{2,}/g

/**
 * The spoken form of a reply, or of a reply so far.
 *
 * Safe to call on every token: the result for a prefix of the text is a prefix
 * of the result for the whole.
 */
export function speakableText(text: string): string {
  let spoken = stripCitationMarkers(text ?? '')

  // A line break rather than nothing, so the sentence before the block ends
  // where it did on screen instead of running into the one after it.
  spoken = spoken.replace(FENCED_BLOCK, '\n')
  spoken = spoken.replace(INLINE_CODE, '$1')

  spoken = spoken.replace(IMAGE, ' ')
  spoken = spoken.replace(LINK, '$1')
  spoken = spoken.replace(BARE_URL, ' ')

  // Whatever is still mid-construct at the end of what has arrived. Runs after
  // the rules above so it only ever sees what none of them could resolve —
  // during a code block that is the entire block, which is why no part of one
  // is spoken on its way past.
  spoken = spoken.replace(PENDING_TAIL, '')

  spoken = spoken.replace(LINE_PREFIX, '')
  spoken = spoken.replace(BULLET, '')
  spoken = spoken.replace(RULE_RUN, ' ')
  spoken = spoken.replace(SYMBOLS, ' ')

  return spoken.replace(WHITESPACE, ' ')
}
