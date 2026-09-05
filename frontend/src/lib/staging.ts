/**
 * How long a staged file has left, said the way a person would say it.
 *
 * One home, two renderers. `ArtifactCard` and `ArtifactGrid` both show this
 * and `docs/SPEECH.md` records what the alternative costs — marker stripping
 * lived in three copies and the one that had been missed was the one that
 * spoke. A countdown that reads "in 7 days" on the card and "in 6 days" in the
 * grid is the same class of bug with a smaller blast radius.
 *
 * **Relative, never a date.** "clears on 11 September" makes the reader do
 * arithmetic to answer the only question they have, which is whether they need
 * to act now. It also goes stale on screen in a way "in 6 days" does not: a
 * card rendered on Tuesday and read on Thursday shows a date that is still
 * correct and a sense of urgency that is not.
 *
 * **Rounded down, never up.** "in 2 days" for something with 2 days and 20
 * hours left is a promise the sweeper keeps early rather than late. Telling
 * someone they have three days when they have two is how a product loses work
 * it said it would hold.
 */

/** Seconds in the units this module counts in. */
const HOUR = 60 * 60;
const DAY = 24 * HOUR;

/**
 * "in 6 days", "in 4 hours", "very soon" — what to put after "clears".
 *
 * `now` is injectable so the tests do not depend on the clock. Defaulted
 * rather than required because every real caller means "now" and a component
 * threading a timestamp through for the sake of testability is how a render
 * ends up showing a moment that has passed.
 */
export function clearsIn(expiresAt: number, now: number = Date.now() / 1000): string {
  const left = expiresAt - now;

  // Already due. It has not gone yet — the sweep runs daily, so a file can sit
  // a little past its window — and claiming a duration here would be a number
  // counting the wrong way. "Very soon" is the honest version of "I don't know
  // exactly, and it isn't long."
  if (left <= 0) return 'very soon';

  if (left >= DAY) {
    // **Rounded, not floored, and the daily sweep is what makes that safe.**
    // Flooring read as an off-by-one on the case that matters most: a file
    // staged one second ago has 6.9999 days left, so the card said "in 6 days"
    // the instant it appeared. Measured in the harness, which is the only
    // reason it was caught — the unit tests passed whole numbers in and got
    // whole numbers back.
    //
    // Rounding can overstate by up to twelve hours, and that costs nothing
    // here because `sweep` runs once a day: a file is not removed at its
    // expiry but at the first sweep after it, so there is already up to a day
    // of grace sitting behind the number.
    const days = Math.max(1, Math.round(left / DAY));
    return `in ${days} ${days === 1 ? 'day' : 'days'}`;
  }

  if (left >= HOUR) {
    const hours = Math.floor(left / HOUR);
    return `in ${hours} ${hours === 1 ? 'hour' : 'hours'}`;
  }

  // Under an hour. Minutes would be a precision nothing here has — the sweep
  // is daily — and a ticking number invites watching something that does not
  // reward it.
  return 'within the hour';
}

/**
 * The whole line, so the two surfaces cannot phrase it differently either.
 *
 * Names the way out in the same breath as the deadline. A countdown with no
 * stated remedy reads as a threat; "unless you save it" is the sentence that
 * makes the Save button beside it make sense.
 */
export function clearsLabel(expiresAt: number, now?: number): string {
  return `clears ${clearsIn(expiresAt, now)} unless you save it`;
}
