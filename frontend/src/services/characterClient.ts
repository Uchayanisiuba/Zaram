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
    // A list of rows reads each row's id. `String(row)` was `[object Object]`
    // the moment the backend began sending rows instead of bare names.
    if (Array.isArray(voices)) {
      return voices.map((v) => (v && typeof v === 'object' ? str((v as { id?: unknown }).id) : String(v))).filter(Boolean);
    }
    if (voices && typeof voices === 'object') return Object.keys(voices as object);
    return [];
  } catch {
    return [];
  }
}

/** One voice in the pack, as the dated local manifest and the local cache know it. */
export interface VoiceEntry {
  id: string;
  /** "Heart", "Fable" — the part after the prefix, for display. */
  name: string;
  language: string;
  languageCode: string;
  gender: 'female' | 'male' | 'unknown';
  /** The upstream author's own rating of how well the voice was trained, A best.
   *  `null` where he gave none — never a letter Zaram made up. */
  grade: string | null;
  sizeBytes: number;
  /** On this machine now, read from the cache. */
  installed: boolean;
  /** What the voice needs that a base install lacks ("espeak-ng", "misaki[ja]"). */
  requires: string | null;
  /** The voice that speaks when none is chosen. */
  isDefault: boolean;
}

export interface VoiceCatalogue {
  /** When the manifest was written; the list is knowledge with a date on it. */
  generated: string | null;
  voices: VoiceEntry[];
}

function toVoiceEntry(raw: unknown): VoiceEntry | null {
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Record<string, unknown>;
  const id = str(r.id);
  if (!id) return null;
  const gender = str(r.gender);
  return {
    id,
    name: str(r.name) || id,
    language: str(r.language) || 'Unknown',
    languageCode: str(r.language_code),
    gender: gender === 'female' || gender === 'male' ? gender : 'unknown',
    grade: str(r.grade) || null,
    sizeBytes: typeof r.size_bytes === 'number' ? r.size_bytes : 0,
    installed: r.installed === true,
    requires: str(r.requires) || null,
    isDefault: r.default === true,
  };
}

/**
 * Every voice in the pack, with which are already on this machine.
 *
 * Never throws, for the reason `fetchVoices` does not: a voice list that cannot
 * be fetched must not stop someone naming their assistant. An empty catalogue
 * is the honest result of a failed request.
 */
export async function fetchVoiceCatalogue(signal?: AbortSignal): Promise<VoiceCatalogue> {
  try {
    const res = await fetch(`${API_BASE}/voice/voices`, { signal });
    if (!res.ok) return { generated: null, voices: [] };
    const data = (await res.json()) as { generated?: unknown; voices?: unknown };
    const rows = Array.isArray(data.voices) ? data.voices : [];
    return {
      generated: str(data.generated) || null,
      voices: rows.map(toVoiceEntry).filter((v): v is VoiceEntry => v !== null),
    };
  } catch {
    return { generated: null, voices: [] };
  }
}

/* ============================================================================
 * Active Provider Voices (Tier-Aware)
 * ============================================================================ */

export interface ActiveVoiceEntry {
  id: string;
  name: string;
  language: string;
  languageCode: string;
  gender: 'female' | 'male' | 'unknown';
  provider: string;
  /** Offered at all: not behind a language pack this install lacks. */
  available: boolean;
  /** On this machine now, read off the local cache. `false` means a download. */
  installed: boolean;
  /** What a greyed voice needs (`misaki[ja]`), or null. */
  requires: string | null;
  /** What the download costs. The pack's voices are about half a megabyte each. */
  sizeBytes: number;
  /** The voice that speaks when none has been chosen. */
  default: boolean;
  grade: string | null;
}

export interface ActiveVoiceCatalogue {
  provider: string | null;
  activeTier: string | null;
  voices: ActiveVoiceEntry[];
  providerHealth: string;
}

export async function fetchActiveVoiceCatalogue(signal?: AbortSignal): Promise<ActiveVoiceCatalogue> {
  try {
    const res = await fetch(`${API_BASE}/voice/voices/active`, { signal });
    if (!res.ok) return { provider: null, activeTier: null, voices: [], providerHealth: 'unavailable' };
    // The backend speaks snake_case. This was cast straight to camelCase types, so
    // `activeTier`, `providerHealth` and `languageCode` were always undefined and the
    // line under the list said "unknown tier".
    const raw = (await res.json()) as {
      provider?: string | null;
      active_tier?: string | null;
      provider_health?: string;
      voices?: Array<Record<string, unknown>>;
    };
    return {
      provider: raw.provider ?? null,
      activeTier: raw.active_tier ?? null,
      providerHealth: raw.provider_health ?? 'unknown',
      voices: (raw.voices ?? []).map((v) => ({
        id: String(v.id),
        name: String(v.name ?? v.id),
        language: String(v.language ?? 'unknown'),
        languageCode: String(v.language_code ?? ''),
        gender: (v.gender === 'female' || v.gender === 'male' ? v.gender : 'unknown') as ActiveVoiceEntry['gender'],
        provider: String(v.provider ?? ''),
        available: v.available !== false,
        // Absent means a provider with nothing to download, which is on hand.
        installed: v.installed !== false,
        requires: typeof v.requires === 'string' ? v.requires : null,
        sizeBytes: typeof v.size_bytes === 'number' ? v.size_bytes : 0,
        default: v.default === true,
        grade: typeof v.grade === 'string' ? v.grade : null,
      })),
    };
  } catch {
    return { provider: null, activeTier: null, voices: [], providerHealth: 'unavailable' };
  }
}

/** Fetch one voice. The backend records it in the egress log before the first byte. */
export async function downloadVoice(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/voice/voices/${encodeURIComponent(id)}/download`, {
    method: 'POST',
    headers: CLIENT_HEADER,
  });
  await readOrThrow(res);
}

/* ============================================================================
 * 4-Tier Voice Pipeline: Tier Management
 * ============================================================================ */

export interface TierStatusEntry {
  provider: string;
  eligible: boolean;
  /** False while the engine behind the tier is a placeholder that cannot speak yet. */
  implemented?: boolean;
  reason: string;
  description: string;
  requires_cloud: boolean;
  requires_gpu: boolean;
}

export interface TierStatus {
  active_tier: string | null;
  active_provider: string | null;
  auto_tier_enabled: boolean;
  prefer_local: boolean;
  tier_status: Record<string, TierStatusEntry>;
  fallback_tier?: string;
}

export async function fetchTierStatus(signal?: AbortSignal): Promise<TierStatus> {
  try {
    const res = await fetch(`${API_BASE}/voice/tier`, { signal });
    if (!res.ok) return { active_tier: null, active_provider: null, auto_tier_enabled: false, prefer_local: true, tier_status: {} };
    return (await res.json()) as TierStatus;
  } catch {
    return { active_tier: null, active_provider: null, auto_tier_enabled: false, prefer_local: true, tier_status: {} };
  }
}

export async function selectTier(tier: string): Promise<{ selected_tier: string; provider: string; reason: string }> {
  const res = await fetch(`${API_BASE}/voice/tier/select`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...CLIENT_HEADER },
    body: JSON.stringify({ tier }),
  });
  return readOrThrow(res) as Promise<{ selected_tier: string; provider: string; reason: string }>;
}

export async function enableAutoTier(): Promise<{ selected_tier: string; provider: string; reason: string }> {
  const res = await fetch(`${API_BASE}/voice/tier/auto`, {
    method: 'POST',
    headers: CLIENT_HEADER,
  });
  return readOrThrow(res) as Promise<{ selected_tier: string; provider: string; reason: string }>;
}

/* ============================================================================
 * Hardware Profile
 * ============================================================================ */

export interface HardwareProfile {
  gpu_vendor: string;
  gpu_name: string;
  total_vram_gb: number | null;
  free_vram_gb: number | null;
  total_system_ram_gb: number | null;
  free_system_ram_gb: number | null;
  cloud_llm_active: boolean;
  cloud_llm_provider: string | null;
  local_llm_active: boolean;
  local_llm_model_id: string | null;
  local_llm_vram_footprint_gb: number | null;
  os_name: string;
  arch: string;
}

export async function fetchHardwareProfile(signal?: AbortSignal): Promise<HardwareProfile> {
  try {
    const res = await fetch(`${API_BASE}/voice/hardware`, { signal });
    if (!res.ok) {
      return {
        gpu_vendor: 'unknown',
        gpu_name: 'unknown',
        total_vram_gb: null,
        free_vram_gb: null,
        total_system_ram_gb: null,
        free_system_ram_gb: null,
        cloud_llm_active: false,
        cloud_llm_provider: null,
        local_llm_active: false,
        local_llm_model_id: null,
        local_llm_vram_footprint_gb: null,
        os_name: 'unknown',
        arch: 'unknown',
      };
    }
    return (await res.json()) as HardwareProfile;
  } catch {
    return {
      gpu_vendor: 'unknown',
      gpu_name: 'unknown',
      total_vram_gb: null,
      free_vram_gb: null,
      total_system_ram_gb: null,
      free_system_ram_gb: null,
      cloud_llm_active: false,
      cloud_llm_provider: null,
      local_llm_active: false,
      local_llm_model_id: null,
      local_llm_vram_footprint_gb: null,
      os_name: 'unknown',
      arch: 'unknown',
    };
  }
}

/* ============================================================================
 * Voice Asset Cleanup
 * ============================================================================ */

export interface CacheStatus {
  total_voices_cached: number;
  total_size_bytes: number;
  total_size_mb: number;
  keep_voice: string;
  keep_voice_size_bytes: number;
  deletable_voices: number;
  deletable_size_bytes: number;
  deletable_size_mb: number;
  by_backend: Record<string, { count: number; size_bytes: number; voices: string[] }>;
}

export async function fetchCacheStatus(keepVoice: string = '', signal?: AbortSignal): Promise<CacheStatus> {
  try {
    const res = await fetch(`${API_BASE}/voice/cache/status?keep_voice=${encodeURIComponent(keepVoice)}`, { signal });
    if (!res.ok) throw new Error('Failed to fetch cache status');
    return (await res.json()) as CacheStatus;
  } catch {
    return {
      total_voices_cached: 0,
      total_size_bytes: 0,
      total_size_mb: 0,
      keep_voice: keepVoice,
      keep_voice_size_bytes: 0,
      deletable_voices: 0,
      deletable_size_bytes: 0,
      deletable_size_mb: 0,
      by_backend: {},
    };
  }
}

export interface CleanupReport {
  deleted_count: number;
  freed_bytes: number;
  freed_mb: number;
  kept_count: number;
  dry_run: boolean;
  errors: string[];
}

export async function cleanupVoiceCache(keepVoice: string, dryRun: boolean): Promise<CleanupReport> {
  const res = await fetch(`${API_BASE}/voice/cache/cleanup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...CLIENT_HEADER },
    body: JSON.stringify({ keep_voice: keepVoice, dry_run: dryRun }),
  });
  const data = await readOrThrow(res);
  return data as unknown as CleanupReport;
}
