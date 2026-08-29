/**
 * The first-run cloud key: choose a provider, paste a key, and be told the truth.
 *
 * `FirstRunPanel` has rendered a "use a cloud key" offer since it was built,
 * greyed out, with its own docstring naming the reason: *"Installing an engine,
 * pulling a model and storing a cloud key each need an executor that does not
 * exist yet."* This is that executor for the third one, and it is the third
 * one because it is the only one whose backend already exists —
 * `POST /providers/cloud` stores the configuration and is **effective without
 * a restart**, which is what makes an offer here honest rather than a promise
 * about the next launch.
 *
 * Four rules, each of which is easy to break by making the screen friendlier.
 *
 * **Never claim the key works.** The backend makes no network call, so a 200
 * means "configured" and nothing else. Rule 7g puts the first request behind
 * the user's consent — it happens on their first message, where the egress
 * gate logs it. A green tick reading "Connected!" would be a claim this code
 * cannot support, and the user would discover it was wrong at the worst
 * moment: mid-question, with a wall of provider error text.
 *
 * **The data policy is shown while they are choosing, not after.** The
 * catalogue's `note` carries the honest sentence — for the free tiers it says
 * outright that prompts are logged and may be trained on. `CLAUDE.md` is
 * explicit that Zaram is the product that can say so: *"add a free key — your
 * prompts train Google, and Zaram will tell you every time one goes."* It sits
 * under the picker where it is unavoidable, not behind a disclosure.
 *
 * **`selectable_by_default` is not this screen's business.** That rule stops
 * *Zaram* routing to a provider whose terms are unknown. It must never stop a
 * person choosing one knowingly, which is the distinction between a consent
 * gate and a paternalism gate. Every available catalogue entry is offered.
 *
 * **Nothing here opens a socket.** `/providers/catalogue` is a shipped
 * manifest that reads no files and opens no sockets, and connecting stores
 * configuration. The whole screen is loopback, which is what lets it run
 * before the user has consented to anything.
 */
import { useEffect, useMemo, useState } from 'react';

import {
  connectCloudProvider,
  fetchProviderCatalogue,
  type CatalogueProvider,
  type ProviderCatalogue,
} from '@/services/settingsClient';

interface CloudKeyFormProps {
  /** Called after a provider is configured, so readiness can be asked again. */
  onConnected: () => void;
}

type Phase =
  | { name: 'loading' }
  | { name: 'unavailable' }
  | { name: 'ready' }
  | { name: 'saving' }
  | { name: 'saved'; provider: string }
  | { name: 'failed'; message: string };

/**
 * Open a page in the user's own browser, if the desktop shell offers it.
 *
 * The window is hardened — `setWindowOpenHandler` denies every new window and
 * `will-navigate` is blocked — so an `<a href>` to a provider's dashboard is
 * inert. Rather than render a link that silently does nothing, this uses the
 * shell bridge when it exists and falls back to showing the address as text
 * the user can read and type. A dead link on a setup screen is worse than no
 * link: it reads as the product being broken at the first thing it asks of you.
 */
function openInBrowser(url: string): boolean {
  const shell = (window as unknown as {
    zaram?: { shell?: { openExternal?: (u: string) => unknown } };
  }).zaram?.shell;
  if (typeof shell?.openExternal !== 'function') return false;
  try {
    shell.openExternal(url);
    return true;
  } catch {
    return false;
  }
}

export default function CloudKeyForm({ onConnected }: CloudKeyFormProps) {
  const [catalogue, setCatalogue] = useState<ProviderCatalogue | null>(null);
  const [phase, setPhase] = useState<Phase>({ name: 'loading' });
  const [providerId, setProviderId] = useState('');
  const [apiKey, setApiKey] = useState('');

  useEffect(() => {
    let live = true;
    fetchProviderCatalogue()
      .then((cat) => {
        if (!live) return;
        setCatalogue(cat);
        setPhase({ name: 'ready' });
      })
      .catch(() => {
        // Same posture as `useReadiness`: a failed probe is not a claim about
        // the world. The offer stays, and says it cannot be carried out now.
        if (live) setPhase({ name: 'unavailable' });
      });
    return () => {
      live = false;
    };
  }, []);

  /** Entries a key can actually be pasted into.
   *
   *  `AuthStyle.NONE` is a local server on loopback — LM Studio, TabbyAPI —
   *  which needs no key and is not a cloud provider. Offering it here would
   *  ask for a credential that has nowhere to go.
   */
  const providers = useMemo<CatalogueProvider[]>(
    () => (catalogue?.providers ?? []).filter((p) => p.available && p.auth !== 'none'),
    [catalogue],
  );

  const chosen = providers.find((p) => p.id === providerId) ?? null;

  async function connect() {
    if (!chosen || !apiKey.trim()) return;
    setPhase({ name: 'saving' });
    try {
      await connectCloudProvider({ providerId: chosen.id, apiKey: apiKey.trim() });
      // Cleared on success. The key is stored on the backend now, and leaving
      // it in a form field means it sits in the renderer's memory and in the
      // DOM for the rest of the session for no purpose.
      setApiKey('');
      setPhase({ name: 'saved', provider: chosen.displayName });
      onConnected();
    } catch (error) {
      setPhase({
        name: 'failed',
        message: error instanceof Error ? error.message : 'Zaram could not save that.',
      });
    }
  }

  if (phase.name === 'loading') {
    return <Muted>Reading the provider list…</Muted>;
  }

  if (phase.name === 'unavailable') {
    return <Muted>Zaram could not read its provider list just now. Try again in a moment.</Muted>;
  }

  if (phase.name === 'saved') {
    return (
      <div className="flex flex-col gap-1.5" data-testid="cloud-key-saved">
        <p className="text-sm" style={{ color: 'var(--color-text)' }}>
          {phase.provider} is set up.
        </p>
        {/* The sentence this screen exists to get right. */}
        <Muted>
          Zaram has not contacted them — nothing has left this device. The key is
          tried the first time you send a message, and you will see what goes.
        </Muted>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3" data-testid="cloud-key-form">
      <label className="flex flex-col gap-1.5">
        <span className="text-[10px] uppercase tracking-wider" style={labelStyle}>
          Provider
        </span>
        <select
          value={providerId}
          onChange={(e) => {
            setProviderId(e.target.value);
            if (phase.name === 'failed') setPhase({ name: 'ready' });
          }}
          className="rounded-lg border px-2.5 py-2 text-sm"
          style={fieldStyle}
        >
          <option value="">Choose one…</option>
          {providers.map((p) => (
            <option key={p.id} value={p.id}>
              {p.displayName}
            </option>
          ))}
        </select>
      </label>

      {/* Under the picker, before the key field, and never behind a
          disclosure. This is the sentence that makes a free tier an informed
          choice rather than a trap. */}
      {chosen?.note && (
        <p
          className="text-xs leading-relaxed rounded-lg border px-2.5 py-2"
          style={{
            color: 'var(--color-text-muted)',
            borderColor: 'rgba(255,255,255,0.08)',
            background: 'rgba(255,255,255,0.02)',
          }}
          data-testid="cloud-key-note"
        >
          {chosen.note}
        </p>
      )}

      {chosen?.keyUrl && <KeyLink url={chosen.keyUrl} />}

      <label className="flex flex-col gap-1.5">
        <span className="text-[10px] uppercase tracking-wider" style={labelStyle}>
          Your key
        </span>
        <input
          type="password"
          value={apiKey}
          onChange={(e) => {
            setApiKey(e.target.value);
            if (phase.name === 'failed') setPhase({ name: 'ready' });
          }}
          placeholder="Paste it here"
          autoComplete="off"
          spellCheck={false}
          className="rounded-lg border px-2.5 py-2 text-sm"
          style={fieldStyle}
        />
      </label>

      {phase.name === 'failed' && (
        <p className="text-xs leading-relaxed" style={{ color: '#fca5a5' }} role="alert">
          {phase.message}
        </p>
      )}

      <button
        type="button"
        onClick={connect}
        disabled={!chosen || !apiKey.trim() || phase.name === 'saving'}
        className="self-start rounded-lg border px-3 py-1.5 text-sm transition-colors"
        style={{
          borderColor: 'var(--color-cyan-light)',
          background: 'rgba(125,211,252,0.08)',
          color: 'var(--color-text)',
          opacity: !chosen || !apiKey.trim() ? 0.45 : 1,
          cursor: !chosen || !apiKey.trim() ? 'default' : 'pointer',
        }}
      >
        {phase.name === 'saving' ? 'Saving…' : 'Save key'}
      </button>

      {/* "Save", not "Connect" or "Verify". The button says exactly what
          happens, and what happens is that a value is written to disk. */}
      <Muted>Nothing is sent anywhere when you save this.</Muted>
    </div>
  );
}

function KeyLink({ url }: { url: string }) {
  const [copiedOut, setCopiedOut] = useState(false);

  return (
    <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
      {copiedOut ? 'Opened in your browser: ' : "Don't have one? "}
      <button
        type="button"
        onClick={() => setCopiedOut(openInBrowser(url))}
        className="underline underline-offset-2"
        style={{ color: 'var(--color-cyan-light)', cursor: 'pointer' }}
      >
        {url}
      </button>
    </p>
  );
}

function Muted({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
      {children}
    </p>
  );
}

const labelStyle: React.CSSProperties = {
  color: 'var(--color-text-muted)',
  fontFamily: 'var(--font-display)',
};

const fieldStyle: React.CSSProperties = {
  borderColor: 'rgba(255,255,255,0.10)',
  background: 'rgba(255,255,255,0.03)',
  color: 'var(--color-text)',
};
