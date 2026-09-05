/**
 * Letterhead transport — the name, address and logo every generated document wears.
 *
 * **The backend could put a logo on a document before anything could give it
 * one.** `artifacts/letterhead.py` validated uploads, bounded their size and
 * refused SVG with a written reason; `_masthead` rendered the result; Word
 * carried it through. `Letterhead` was constructed in two places, both from
 * per-request fields, both without a logo — so every document Zaram has ever
 * generated went out unbranded. This is the client that closes that, and it is
 * the same shape of gap `characterClient` was written to close.
 *
 * **`undefined` and `""` are different intentions**, exactly as in
 * `characterClient`: absent leaves a field alone, empty clears it. A store
 * where clearing is impossible makes a mistyped business name permanent.
 *
 * **The logo is fetched separately from everything else.** `GET /letterhead`
 * answers with `hasLogo` and a byte count; the pixels come from
 * `/letterhead/logo` and only when something is going to draw them. The stored
 * value is a base64 `data:` URI and can be most of a megabyte — WeasyPrint is
 * called with no `base_url`, so a path cannot resolve and a URL is banned
 * outright, which leaves embedding as the only form that works in both the
 * preview and the PDF.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

/** What the interface needs to render the controls: everything except the
 *  pixels. */
export interface Letterhead {
  name: string;
  lines: string[];
  hasLogo: boolean;
  /** Size of the stored data URI. Shown so "Replace" can say what it is
   *  replacing, and so a user who uploaded something enormous can see why. */
  logoBytes: number;
}

export class LetterheadError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'LetterheadError';
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
  throw new LetterheadError(detail, response.status);
}

const str = (value: unknown): string => (typeof value === 'string' ? value : '');

function toLetterhead(raw: Record<string, unknown>): Letterhead {
  return {
    name: str(raw.name),
    lines: Array.isArray(raw.lines) ? raw.lines.filter((l): l is string => typeof l === 'string') : [],
    hasLogo: raw.has_logo === true,
    logoBytes: typeof raw.logo_bytes === 'number' ? raw.logo_bytes : 0,
  };
}

export async function fetchLetterhead(signal?: AbortSignal): Promise<Letterhead> {
  return toLetterhead(await readOrThrow(await fetch(`${API_BASE}/letterhead`, { signal })));
}

/** The stored `data:` URI, or empty when none is set.
 *
 *  Empty is an ordinary answer rather than an error — most users have no logo
 *  on their first day, and a 404 for that would put a red line in the console
 *  of a product that is working correctly. */
export async function fetchLetterheadLogo(signal?: AbortSignal): Promise<string> {
  const raw = await readOrThrow(await fetch(`${API_BASE}/letterhead/logo`, { signal }));
  return str(raw.logo);
}

export async function saveLetterhead(update: {
  name?: string;
  lines?: string[];
}): Promise<Letterhead> {
  const body: Record<string, unknown> = {};
  if (update.name !== undefined) body.name = update.name;
  if (update.lines !== undefined) body.lines = update.lines;

  return toLetterhead(
    await readOrThrow(
      await fetch(`${API_BASE}/letterhead`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    ),
  );
}

/**
 * Upload a logo the user picked.
 *
 * **The rejection is shown to the user unchanged.** `logo_data_uri` explains
 * which formats are accepted, what the size limit is, and why SVG is refused
 * even though it would be smaller and sharper — because an SVG can carry a
 * remote reference, and a generated document must fetch nothing. Replacing
 * that with "upload failed" would throw away the only sentence that tells
 * someone what to do next.
 *
 * The file is read here rather than posted as multipart because the value is
 * *stored* as base64: posting bytes would mean decoding them on the way in so
 * they could be re-encoded on the way to disk.
 */
export async function uploadLogo(file: File): Promise<Letterhead> {
  const data = await fileToBase64(file);
  return toLetterhead(
    await readOrThrow(
      await fetch(`${API_BASE}/letterhead/logo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // `file.type` can be empty when the OS does not know the extension.
        // Sent as-is rather than guessed: the backend's refusal names the type
        // it saw, and inventing one here would make that message a lie.
        body: JSON.stringify({ data, content_type: file.type }),
      }),
    ),
  );
}

export async function clearLogo(): Promise<Letterhead> {
  return toLetterhead(
    await readOrThrow(
      await fetch(`${API_BASE}/letterhead/logo`, { method: 'DELETE' }),
    ),
  );
}

/** Base64 without the `data:` prefix, which the backend rebuilds from the
 *  declared type so the stored URI cannot disagree with what was checked. */
function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new LetterheadError('That file could not be read.', 0));
    reader.onload = () => {
      const result = typeof reader.result === 'string' ? reader.result : '';
      const comma = result.indexOf(',');
      resolve(comma === -1 ? '' : result.slice(comma + 1));
    };
    reader.readAsDataURL(file);
  });
}

/**
 * What Zaram read out of a document the user already sends. Not yet in use.
 *
 * **A proposal is deliberately not a letterhead**, and the two must not be
 * collapsed. `template_profile.py` keeps them as different types for the same
 * reason this client keeps them as different calls: "extracted" and "approved"
 * have to stay distinguishable, and the review is the gap between them.
 */
export interface ProposedField {
  value: string;
  /** The line it was read from. Not decoration — confirming "yes, that is my
   *  address" is a far easier question than "what is your address", but only
   *  with the source line in view. */
  evidence: string;
  confidence: number;
}

export interface MissingField {
  name: string;
  reason: string;
  /** What to ask, written for a person by the backend. */
  question: string;
}

export interface TemplateProposal {
  name: ProposedField | null;
  addressLines: ProposedField[];
  logo: ProposedField | null;
  termsDays: ProposedField | null;
  currency: ProposedField | null;
  numbering: ProposedField | null;
  missing: MissingField[];
}

function toField(raw: unknown): ProposedField | null {
  if (!raw || typeof raw !== 'object') return null;
  const f = raw as Record<string, unknown>;
  return {
    value: str(f.value),
    evidence: str(f.evidence),
    confidence: typeof f.confidence === 'number' ? f.confidence : 0,
  };
}

/**
 * Read a company's identity out of one of their own documents.
 *
 * **Nothing is applied by this call.** It proposes; `adoptTemplate` saves what
 * the person confirmed. A user who closes the review without looking must not
 * have adopted an identity they never saw.
 */
export async function readTemplate(file: File): Promise<TemplateProposal> {
  const data = await fileToBase64(file);
  const raw = await readOrThrow(
    await fetch(`${API_BASE}/letterhead/from-document`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data, filename: file.name }),
    }),
  );
  const lines = Array.isArray(raw.address_lines) ? raw.address_lines : [];
  const missing = Array.isArray(raw.missing) ? raw.missing : [];
  return {
    name: toField(raw.name),
    addressLines: lines.map(toField).filter((f): f is ProposedField => f !== null),
    logo: toField(raw.logo),
    termsDays: toField(raw.terms_days),
    currency: toField(raw.currency),
    numbering: toField(raw.numbering),
    missing: missing.map((m) => {
      const entry = (m ?? {}) as Record<string, unknown>;
      return {
        name: str(entry.name),
        reason: str(entry.reason),
        question: str(entry.question),
      };
    }),
  };
}

/**
 * Save what the person confirmed in the review.
 *
 * **Values, not a proposal id.** A server-side "adopt what you extracted"
 * would discard the corrections made in the review — and the user would find
 * out when a client did.
 */
export async function adoptTemplate(confirmed: {
  name: string;
  lines: string[];
  logo: string;
}): Promise<Letterhead> {
  return toLetterhead(
    await readOrThrow(
      await fetch(`${API_BASE}/letterhead/adopt`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(confirmed),
      }),
    ),
  );
}
