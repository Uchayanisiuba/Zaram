/**
 * Character transport — what this person calls Zaram, how it writes, who speaks.
 *
 * The backend has had `GET`/`POST /character` and a bounded store behind them
 * for days, and nothing in the interface ever called either. A user could not
 * name it. This is the client that closes that.
 *
 * **Three fields, one object, one write.** A name, a manner and a voice are a
 * character to the person setting them, and `set_character` is deliberately a
 * single writer — splitting them would let an interface save two and fail on
 * the third, leaving a half-applied character nobody chose.
 *
 * **`undefined` and `""` are different intentions and must stay so.** Absent
 * leaves a field alone; an empty string clears it back to the default. That is
 * why every field here is optional rather than defaulted — collapsing them
 * would make "I have not touched the manner" indistinguishable from "remove my
 * manner", and the second is a thing a user does on purpose.
 *
 * **None of this can change what Zaram says it is**, and that guarantee lives
 * in `core/identity.py` rather than here: the name and manner are placed
 * *before* the rules about self-description, so the last instruction a model
 * reads is the true one. This client cannot weaken it and must never try to.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

/** Marks a request as coming from Zaram's own interface, forcing a preflight
 *  that the backend checks against its origin allow-list. Same reasoning as
 *  `settingsClient`: it is a label, never a credential. */
const CLIENT_HEADER = { 'X-Zaram-Client': 'zaram-ui' } as const;

export interface Character {
  assistantName: string;
  manner: string;
  voice: string;
  /** What it is called when the user has not named it. Sent by the backend so
   *  the interface never hardcodes the product's own name to draw a
   *  placeholder. */
  defaultName: string;
  /** Which voice speaks when the user has not chosen one. Empty when speech is
   *  not installed, and empty is a real answer: the interface says nothing
   *  rather than naming a voice this machine cannot produce. */
  defaultVoice: string;
}

export class CharacterError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'CharacterError';
  }
}

async function readOrThrow(response: Response): Promise<Record<string, unknown>> {
  if (response.ok) return (await response.json()) as Record<string, unknown>;

  let detail = response.statusText || `HTTP ${response.status}`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === 'string' && body.detail) detail = body.detail;
  } catch {
    /* not JSON; the status text will have to do */
  }
  throw new CharacterError(detail, response.status);
}

const str = (value: unknown): string => (typeof value === 'string' ? value : '');

function toCharacter(raw: Record<string, unknown>): Character {
  return {
    assistantName: str(raw.assistant_name),
    manner: str(raw.manner),
    voice: str(raw.voice),
    // Falls back to the product name only if the backend sent nothing, which
    // it always does. A blank placeholder would be worse than a hardcoded one.
    defaultName: str(raw.default_name) || 'Zaram',
    // Deliberately *not* defaulted. Empty means the backend has no voice to
    // name — no speech extra — and the interface must render no claim rather
    // than a plausible one. A hardcoded voice id here would be a status
    // indicator over invented data.
    defaultVoice: str(raw.default_voice),
  };
}

export async function fetchCharacter(signal?: AbortSignal): Promise<Character> {
  return toCharacter(await readOrThrow(await fetch(`${API_BASE}/character`, { signal })));
}

/**
 * Save any of the three. Omit a field to leave it untouched; pass `""` to clear
 * it back to the default.
 *
 * The response is the stored value, not the submitted one — the backend
 * collapses whitespace and bounds the length, so a name of 200 characters comes
 * back at 48. Rendering what was sent instead would show the user a value that
 * is not what Zaram will use.
 */
export async function saveCharacter(update: {
  assistantName?: string;
  manner?: string;
  voice?: string;
}): Promise<Character> {
  const body: Record<string, string> = {};
  if (update.assistantName !== undefined) body.assistant_name = update.assistantName;
  if (update.manner !== undefined) body.manner = update.manner;
  if (update.voice !== undefined) body.voice = update.voice;

  return toCharacter(
    await readOrThrow(
      await fetch(`${API_BASE}/character`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...CLIENT_HEADER },
        body: JSON.stringify(body),
      }),
    ),
  );
}

/**
 * The voices speech can actually use.
 *
 * Empty is the ordinary state rather than a fault: voice ships as an optional
 * extra, so a base install has none and the interface must say that instead of
 * drawing a picker over nothing. Never throws — a voice list that cannot be
 * fetched must not stop someone naming their assistant.
 */
export async function fetchVoices(signal?: AbortSignal): Promise<string[]> {
  try {
    const res = await fetch(`${API_BASE}/voice/voices`, { signal });
    if (!res.ok) return [];
    const data = (await res.json()) as { voices?: unknown };
    const voices = data.voices;
    if (Array.isArray(voices)) return voices.map(String);
    if (voices && typeof voices === 'object') return Object.keys(voices as object);
    return [];
  } catch {
    return [];
  }
}
