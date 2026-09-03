/**
 * Settings transport — the controls that change how Zaram behaves.
 *
 * Separate from `egressClient`, which reads the record of what left. This one
 * writes: which providers Zaram may call, which model answers, how far it
 * leans on the cloud, and the switch that stops everything outbound at once.
 *
 * Three properties are load-bearing and are asserted in
 * `settingsClient.test.ts` rather than left to convention.
 *
 * **A key goes out and never comes back.** `connectCloudProvider` sends one;
 * nothing in this file has a function that returns one. `CloudConnection`
 * carries `keyTail` — four characters, enough to tell one key from another and
 * not enough to use — because the local API has no authentication and an
 * endpoint that returned a key would hand it to any process on the machine.
 *
 * **Mutating calls carry `X-Zaram-Client`.** The header is not on the CORS
 * safelist, so a browser must preflight the request, and the preflight is
 * checked against the backend's origin allow-list. Without it, a form post from
 * any page the user happens to have open could repoint Zaram's cloud endpoint —
 * CORS does not prevent a simple request being *sent*, only its response being
 * read, and an attacker setting an endpoint does not need to read anything.
 *
 * **A failure carries the backend's own sentence.** The refusals in
 * `cloud_config.py` are written for a person to act on — "Zaram cannot call
 * Claude directly yet…" — and replacing them with "Request failed" throws away
 * the part that took the thought.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

/** Marks a request as coming from Zaram's own interface. See the header. */
const CLIENT_HEADER = { 'X-Zaram-Client': 'zaram-ui' } as const;

/** A failure with the backend's message preserved. */
export class SettingsError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'SettingsError';
  }
}

async function readOrThrow(response: Response): Promise<unknown> {
  if (response.ok) return response.json();

  // FastAPI puts the sentence in `detail`. Falling back to the status text
  // rather than to a generic string keeps the failure identifiable when the
  // body is not what we expect — e.g. a proxy answering instead of the backend.
  let detail = response.statusText || `HTTP ${response.status}`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === 'string' && body.detail) detail = body.detail;
  } catch {
    /* not JSON; keep the status text */
  }
  throw new SettingsError(detail, response.status);
}

async function get(path: string): Promise<unknown> {
  return readOrThrow(await fetch(`${API_BASE}${path}`));
}

async function send(path: string, method: 'POST' | 'PUT' | 'DELETE', body?: unknown) {
  return readOrThrow(
    await fetch(`${API_BASE}${path}`, {
      method,
      headers: { ...CLIENT_HEADER, ...(body ? { 'Content-Type': 'application/json' } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
    }),
  );
}

// --------------------------------------------------------------- providers

/** One entry in the dated manifest of providers a person can pick from. */
export interface CatalogueProvider {
  id: string;
  displayName: string;
  baseUrl: string;
  /** Whether Zaram can call it today. `false` entries are shown, greyed, with
   *  `note` — hidden and "quietly listed as working" are both worse. */
  available: boolean;
  /** Why, in one sentence the user can act on. Required for unavailable ones. */
  note: string;
  /** Where the user goes to get a key. Displayed and opened by them, never
   *  fetched — rule 7g. */
  keyUrl: string;
  /** `openai` | `native` | `unverified`. An unverified entry can still be
   *  connected when the user supplies the base URL themselves. */
  compatibility: string;
  /** `none` means a local server on loopback, so no key is needed. */
  auth: string;
}

export interface ProviderCatalogue {
  /** The date every URL was read from provider documentation. Shown, always:
   *  a manifest without a visible date is a claim about the present that
   *  quietly becomes a claim about the past. */
  generated: string;
  providers: CatalogueProvider[];
}

export async function fetchProviderCatalogue(): Promise<ProviderCatalogue> {
  const raw = (await get('/providers/catalogue')) as {
    generated: string;
    providers: Array<Record<string, unknown>>;
  };
  return {
    generated: raw.generated,
    providers: (raw.providers ?? []).map((p) => ({
      id: String(p.id),
      displayName: String(p.display_name ?? p.id),
      baseUrl: String(p.base_url ?? ''),
      available: p.available === true,
      note: String(p.note ?? ''),
      keyUrl: String(p.key_url ?? ''),
      compatibility: String(p.compatibility ?? ''),
      auth: String(p.auth ?? ''),
    })),
  };
}

/** A provider Zaram is currently connected to. Never carries a key. */
export interface CloudConnection {
  providerId: string;
  displayName: string;
  baseUrl: string;
  /** Last four characters of the key, or null. Identifies; cannot be used. */
  keyTail: string | null;
  locality: 'local' | 'cloud';
}

export interface CloudStatus {
  connections: CloudConnection[];
  configured: boolean;
  generated: string;
}

function toCloudStatus(raw: Record<string, unknown>): CloudStatus {
  const rows = (raw.connections ?? []) as Array<Record<string, unknown>>;
  return {
    configured: raw.configured === true,
    generated: String(raw.generated ?? ''),
    connections: rows.map((c) => ({
      providerId: String(c.provider_id),
      displayName: String(c.display_name ?? c.provider_id),
      baseUrl: String(c.base_url ?? ''),
      keyTail: typeof c.key_tail === 'string' ? c.key_tail : null,
      locality: c.locality === 'local' ? 'local' : 'cloud',
    })),
  };
}

export async function fetchCloudStatus(): Promise<CloudStatus> {
  return toCloudStatus((await get('/providers/cloud')) as Record<string, unknown>);
}

/**
 * Connect a provider. Returns the full status, so a caller never has to guess
 * what changed.
 *
 * **No network call happens as a result of this** — the backend stores the
 * configuration and stops. So a success means "configured", never "reachable"
 * and never "the key is valid". Saying otherwise would require testing the key,
 * and rule 7g puts that behind the user's consent: it happens on the first
 * message, where the egress gate logs and confirms it.
 */
export async function connectCloudProvider(input: {
  providerId?: string;
  baseUrl?: string;
  apiKey?: string;
}): Promise<CloudStatus> {
  const raw = (await send('/providers/cloud', 'POST', {
    provider_id: input.providerId ?? null,
    base_url: input.baseUrl ?? null,
    api_key: input.apiKey ?? null,
  })) as Record<string, unknown>;
  return toCloudStatus(raw);
}

export async function disconnectCloudProvider(providerId: string): Promise<CloudStatus> {
  const raw = (await send(
    `/providers/cloud?provider_id=${encodeURIComponent(providerId)}`,
    'DELETE',
  )) as Record<string, unknown>;
  return toCloudStatus(raw);
}

// ------------------------------------------------------------------ models

/** A model the provider layer discovered. */
export interface DiscoveredModel {
  id: string;
  displayName: string;
  provider: string;
  locality: 'local' | 'cloud' | string;
  /** Null when the provider's terms are not established. Rendered as
   *  "unknown", never as a reassuring default — an unestablished policy is not
   *  a quiet yes. */
  dataPolicy: string | null;
  /** Whether Zaram may route here without being asked. False is normal for
   *  cloud models and is the reason one has to be chosen deliberately. */
  selectableByDefault: boolean;
  /** Whether this model can sit in VRAM beside the embedding model.
   *
   *  **Three values, and `null` is not a quiet yes.** It means the question
   *  could not be answered — no accelerator, a card whose capacity cannot be
   *  read (Metal and DirectML report nothing), or a model that does not state
   *  its size. The backend never promotes `null` to `true` and neither may
   *  this: on the one fact a user is most likely to check, an admission beats
   *  a confident guess. */
  fitsResident: boolean | null;
  /** On-disk size, or `null` where the provider does not report one.
   *
   *  **Weights alone.** Not what the model claims on the card — see
   *  `residentCostBytes`, and never compare this against the budget. */
  sizeBytes: number | null;
  /** What the model actually claims in VRAM: weights plus its own KV cache.
   *
   *  This is the number `fitsResident` is decided on, so it is the number the
   *  reason has to quote. Quoting `sizeBytes` instead was correct only while
   *  the cache allowance was held back from the budget rather than charged to
   *  the model; since it moved, a model can be graded too large while its
   *  weights sit under the budget, and the row contradicts its own verdict.
   *
   *  `null` where the provider reports no size — every OpenAI-compatible
   *  server, since no such route carries a memory figure. */
  residentCostBytes: number | null;
  /** How much VRAM a chat model may claim on this machine, or `null`.
   *
   *  Carried so the reason can name numbers. "21.6 GB, and this machine has
   *  11.7 GB for a chat model" is a sentence someone can act on; "does not
   *  fit" is a verdict they can only accept. */
  residentBudgetBytes: number | null;
  /** `llm`, `embedding`, and whatever the provider layer adds later.
   *
   *  Carried because an embedder cannot hold a conversation: Ollama answers
   *  `/api/generate` for `bge-m3` with a 400, so offering it under *Which
   *  model answers* is offering a choice that can only fail. `/readiness`
   *  already excludes embedders from its chat-model count; the picker was the
   *  one surface that did not. */
  category: string;
}

/**
 * The discovered models.
 *
 * **This is a network call for every connected cloud provider**, because
 * discovery asks each one what it offers. It goes through the egress gate, so
 * it is logged and refused by policy like anything else — which is why the
 * interface asks for it on a button rather than on mount.
 */
/**
 * Run discovery again, and return what is there now.
 *
 * **Discovery ran once per backend process and never again.** So an inference
 * server started *after* Zaram was invisible until Zaram itself restarted:
 * measured 30 August 2026 with TabbyAPI serving a model it was confirmed to be
 * answering with, while the model list showed only what was found at boot. To
 * the user that is indistinguishable from Zaram having lost their model.
 *
 * A POST, and never folded into `fetchModels`, for the reason that function
 * already gives: discovery asks every connected cloud provider what it offers,
 * so it is egress. Refreshing from the network stays an explicit act.
 */
export async function rescanModels(): Promise<DiscoveredModel[]> {
  const rows = (await send('/providers/rescan', 'POST')) as Array<Record<string, unknown>>;
  return rows.map(toDiscoveredModel);
}

/** One row as the interface needs it.
 *
 *  Shared by the listing and the rescan rather than written twice: two mappers
 *  for one payload is how a field comes to be read in one place and dropped in
 *  the other, and it is the same argument `hostOf` settled for a citation's
 *  domain. */
function toDiscoveredModel(m: Record<string, unknown>): DiscoveredModel {
  return {
    id: String(m.id),
    displayName: String(m.display_name ?? m.id),
    provider: String(m.provider ?? ''),
    locality: String(m.locality ?? ''),
    dataPolicy: typeof m.data_policy === 'string' ? m.data_policy : null,
    selectableByDefault: m.selectable_by_default === true,
    // `?? null` rather than a boolean coercion, deliberately: `Boolean(null)`
    // is `false`, which would render "too large for this machine" for every
    // model on a Mac — where the answer is genuinely unknown, not no.
    fitsResident: typeof m.fits_resident === 'boolean' ? m.fits_resident : null,
    residentBudgetBytes:
      typeof m.resident_budget_bytes === 'number' ? m.resident_budget_bytes : null,
    sizeBytes: typeof m.size_bytes === 'number' ? m.size_bytes : null,
    residentCostBytes:
      typeof m.resident_cost_bytes === 'number' ? m.resident_cost_bytes : null,
    category: String(m.category ?? ''),
  };
}

export async function fetchModels(): Promise<DiscoveredModel[]> {
  const rows = (await get('/providers/models')) as Array<Record<string, unknown>>;
  return rows.map(toDiscoveredModel);
}

// ----------------------------------------------------------------- routing

export type RoutingPreference = 'prefer_local' | 'auto' | 'prefer_cloud';

export interface RoutingSettings {
  routingPreference: RoutingPreference;
  /** The model the user chose, or null for "let Zaram decide" — which is the
   *  provider layer's vetted selection, not "no model". */
  defaultModel: string | null;
}

export async function fetchRoutingSettings(): Promise<RoutingSettings> {
  const raw = (await get('/routing/preference')) as Record<string, unknown>;
  return {
    routingPreference: (raw.routing_preference as RoutingPreference) ?? 'auto',
    defaultModel: typeof raw.default_model === 'string' ? raw.default_model : null,
  };
}

/** Update either field. Omitting one leaves it alone rather than clearing it. */
export async function updateRoutingSettings(update: {
  routingPreference?: RoutingPreference;
  /** `''` hands the choice back to Zaram. `undefined` leaves it unchanged. */
  defaultModel?: string;
}): Promise<RoutingSettings> {
  const raw = (await send('/routing/preference', 'POST', {
    routing_preference: update.routingPreference ?? null,
    default_model: update.defaultModel ?? null,
  })) as Record<string, unknown>;
  return {
    routingPreference: (raw.routing_preference as RoutingPreference) ?? 'auto',
    defaultModel: typeof raw.default_model === 'string' ? raw.default_model : null,
  };
}

// ------------------------------------------------------------- web search

/**
 * The state of web search, and what still stands between it and working.
 *
 * More than a boolean on purpose. Search is the *first governed source*:
 * turning it on lets a search step be planned, and the per-host rule still
 * decides whether the request may be sent. A screen showing only the switch
 * would have the user turn it on, ask a question, get a refusal, and conclude
 * the feature is broken — so the two remaining obstacles travel with it.
 */
/** When a search is worth running, once search is switched on. */
export type SearchScope = 'local_only' | 'always';

export interface WebSearchStatus {
  /** The effective answer: may a search be planned? */
  on: boolean;
  /** `local_only` searches only when a local model is answering — search
   *  compensates for what the answering model does not know, and a local model
   *  knows least. */
  scope: SearchScope;
  /** What the toggle itself is set to, which differs from `on` when the
   *  environment is overriding it. */
  stored: boolean;
  /** `ZARAM_WEB_SEARCH` is set, so the toggle is not the authority and the
   *  screen must say so rather than showing a control that appears inert. */
  forcedByEnvironment: boolean;
  /** The host a search is addressed to, so the user can find its rule. */
  host: string;
  /** What would happen to a request to that host today. */
  hostPolicy: EgressMode;
  /** The kill switch overrides everything, including this. */
  killSwitch: boolean;
}

function toWebSearch(raw: Record<string, unknown>): WebSearchStatus {
  return {
    on: raw.on === true,
    scope: raw.scope === 'always' ? 'always' : 'local_only',
    stored: raw.stored === true,
    forcedByEnvironment: raw.forced_by_environment === true,
    host: String(raw.host ?? ''),
    hostPolicy: (raw.host_policy as EgressMode) ?? 'deny',
    killSwitch: raw.kill_switch === true,
  };
}

export async function fetchWebSearch(): Promise<WebSearchStatus> {
  return toWebSearch((await get('/search/web')) as Record<string, unknown>);
}

/** Turn web search on or off. Grants no destination anything — see the type. */
export async function setWebSearch(on: boolean): Promise<WebSearchStatus> {
  return toWebSearch((await send('/search/web', 'POST', { on })) as Record<string, unknown>);
}

/** Choose when searching is worth it. Does not turn search on. */
export async function setSearchScope(scope: SearchScope): Promise<WebSearchStatus> {
  return toWebSearch(
    (await send('/search/web', 'POST', { scope })) as Record<string, unknown>,
  );
}

// ------------------------------------------------------------- kill switch

export async function fetchKillSwitch(): Promise<boolean> {
  return ((await get('/egress/killswitch')) as { on?: boolean }).on === true;
}

/** Cut, or restore, everything outbound. Loopback is never affected. */
export async function setKillSwitch(on: boolean): Promise<boolean> {
  return ((await send('/egress/killswitch', 'POST', { on })) as { on?: boolean }).on === true;
}

// ------------------------------------------------------- per-source policy

export type EgressMode = 'allow' | 'ask' | 'deny';

export interface EgressPolicy {
  /** Always "deny". Shown because rule 5's default is the thing worth stating. */
  default: string;
  rules: Record<string, EgressMode>;
  /** Hosts contacted at least once. Offering a decision about a destination
   *  the user has actually met beats asking them to type hostnames. */
  hostsWithoutARule: string[];
}

export async function fetchEgressPolicy(): Promise<EgressPolicy> {
  const raw = (await get('/egress/policy')) as Record<string, unknown>;
  return {
    default: String(raw.default ?? 'deny'),
    rules: (raw.rules ?? {}) as Record<string, EgressMode>,
    hostsWithoutARule: (raw.hosts_without_a_rule ?? []) as string[],
  };
}

export async function setEgressPolicyForHost(host: string, mode: EgressMode): Promise<void> {
  await send('/egress/policy', 'PUT', { host, mode });
}

export async function forgetEgressPolicyForHost(host: string): Promise<void> {
  await send(`/egress/policy/${encodeURIComponent(host)}`, 'DELETE');
}

// ------------------------------------------------------------------ export
//
// Rule 7 — the Spine is exportable in an open format, no lock-in. The exporter
// and its tests were complete for weeks with no route in front of them, so the
// rule was true of the code and false of the product.

export interface ExportManifest {
  formatVersion: number;
  /** `-1` means the store could not be counted, which is not the same as zero.
   *  A zero here is a claim that the user has nothing, and it must be earned. */
  facts: number;
  egressEntries: number;
  generatedDocuments: number;
  formats: string[];
  note: string;
}

export async function fetchExportManifest(): Promise<ExportManifest> {
  const raw = (await get('/export/manifest')) as Record<string, unknown>;
  return {
    formatVersion: Number(raw.format_version ?? 0),
    facts: Number(raw.facts ?? -1),
    egressEntries: Number(raw.egress_entries ?? -1),
    generatedDocuments: Number(raw.generated_documents ?? -1),
    formats: (raw.formats ?? []) as string[],
    note: String(raw.note ?? ''),
  };
}

/**
 * Download everything Zaram holds, as one .zip.
 *
 * Fetched as a blob and handed to the browser rather than pointed at with a
 * plain `<a href>`. Two reasons, and the second is the one that matters: a
 * link cannot report a failure, so a backend that is down produces a broken
 * download with no message — on the one control whose entire purpose is
 * reassuring somebody that leaving is possible.
 */
export async function downloadExport(): Promise<string> {
  const response = await fetch(`${API_BASE}/export`, { headers: CLIENT_HEADER });
  if (!response.ok) {
    throw new SettingsError(
      `The export could not be built (HTTP ${response.status}). Nothing was changed.`,
      response.status,
    );
  }

  const blob = await response.blob();
  // The backend names the file, so the timestamp in it is the moment the
  // export was *built* rather than the moment the browser saved it.
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const named = /filename="([^"]+)"/.exec(disposition);
  const filename = named?.[1] ?? 'zaram-export.zip';

  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  return filename;
}
