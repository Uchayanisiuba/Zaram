/**
 * Choosing a voice, from the whole pack.
 *
 * Asked for 4 October 2026: *"multiple voice options … with all the models
 * and details about them."* The Settings row offered one `<select>` over an
 * empty list, because naming the pack meant asking huggingface.co and rule 7g
 * forbids a network call nobody consented to. The names now come from a dated
 * file in the bundle, so the list is whole before anyone has downloaded a
 * thing.
 *
 * Three states per voice, as the model browser has three, and they are
 * different sentences:
 *
 * *On this machine* — pick it. *Not yet* — a download of about half a
 * megabyte, with its price on the button, and picking it is the same act as
 * fetching it (the button says what it will do, which is rule 7j's consent).
 * *Needs something else* — listed and greyed with what it needs, no button:
 * Japanese and Mandarin need language packs the base install lacks, and
 * offering a choice that fails on the first sentence is a product that looks
 * broken. Greyed, not hidden — disabled capabilities are visible.
 *
 * **The grade is the pack author's, not Zaram's.** It is how well he trained
 * the voice, A best, and is absent where he gave none. Nothing here describes
 * how a voice sounds, because nobody measured that.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, Download, Loader2, Search } from 'lucide-react';

import {
  downloadVoice,
  fetchVoiceCatalogue,
  type VoiceEntry,
} from '@/services/characterClient';

interface Props {
  /** The voice that currently speaks; empty means the shipped default. */
  selected: string;
  /** Called with a voice id that is on this machine. */
  onSelect: (id: string) => void;
}

function size(bytes: number): string {
  if (bytes <= 0) return '';
  return bytes >= 1_000_000 ? `${(bytes / 1_000_000).toFixed(1)} MB` : `${Math.round(bytes / 1000)} kB`;
}

export default function VoiceBrowser({ selected, onSelect }: Props) {
  const [voices, setVoices] = useState<VoiceEntry[]>([]);
  const [generated, setGenerated] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [query, setQuery] = useState('');
  const [fetching, setFetching] = useState<string | null>(null);
  const [failure, setFailure] = useState('');

  const load = useCallback(async () => {
    const catalogue = await fetchVoiceCatalogue();
    setVoices(catalogue.voices);
    setGenerated(catalogue.generated);
    setLoaded(true);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function choose(voice: VoiceEntry) {
    setFailure('');
    if (!voice.installed) {
      setFetching(voice.id);
      try {
        await downloadVoice(voice.id);
        await load();
      } catch (error) {
        setFailure(error instanceof Error ? error.message : 'That voice could not be fetched.');
        setFetching(null);
        return;
      }
      setFetching(null);
    }
    onSelect(voice.id);
  }

  const groups = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const shown = needle
      ? voices.filter(
          (v) =>
            v.id.toLowerCase().includes(needle) ||
            v.name.toLowerCase().includes(needle) ||
            v.language.toLowerCase().includes(needle) ||
            v.gender.includes(needle),
        )
      : voices;
    const byLanguage = new Map<string, VoiceEntry[]>();
    for (const voice of shown) {
      const list = byLanguage.get(voice.language) ?? [];
      list.push(voice);
      byLanguage.set(voice.language, list);
    }
    return [...byLanguage.entries()];
  }, [voices, query]);

  if (loaded && voices.length === 0) {
    return (
      <p data-testid="no-voices" className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
        Zaram’s list of voices could not be read. The voice that is speaking now still works.
      </p>
    );
  }

  return (
    <div data-testid="voice-browser" className="w-full">
      <div className="relative mb-3">
        <Search
          size={14}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2"
          style={{ color: 'var(--color-text-faint)' }}
          aria-hidden
        />
        <input
          data-testid="voice-search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search voices — a name, a language, male or female"
          spellCheck={false}
          className="w-full rounded-lg py-2 pl-9 pr-3 text-sm outline-none"
          style={{
            background: 'var(--color-glass)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text)',
          }}
        />
      </div>

      {failure && (
        <p
          data-testid="voice-browser-error"
          className="mb-3 rounded-lg px-3 py-2 text-xs"
          style={{
            background: 'rgba(180,83,9,0.12)',
            border: '1px solid rgba(180,83,9,0.3)',
            color: 'var(--color-amber-light, #fcd34d)',
          }}
        >
          {failure} Nothing was changed.
        </p>
      )}

      <div className="max-h-80 space-y-4 overflow-auto pr-1">
        {groups.map(([language, list]) => (
          <section key={language} aria-label={language}>
            <h4 className="mb-1.5 text-[11px] uppercase tracking-wide" style={{ color: 'var(--color-text-faint)' }}>
              {language}
            </h4>
            <ul className="space-y-1.5">
              {list.map((voice) => {
                const blocked = voice.requires !== null;
                const active = selected ? selected === voice.id : voice.isDefault;
                const busy = fetching === voice.id;
                return (
                  <li
                    key={voice.id}
                    data-testid={`voice-${voice.id}`}
                    className="flex items-center gap-3 rounded-lg px-3 py-2"
                    style={{
                      background: 'var(--color-glass)',
                      border: `1px solid ${active ? 'var(--color-cyan)' : 'var(--color-border-subtle)'}`,
                      opacity: blocked ? 0.55 : 1,
                    }}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm" style={{ color: 'var(--color-text)' }}>
                        {voice.name}
                        <span className="ml-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                          {voice.gender}
                        </span>
                        {voice.isDefault && (
                          <span className="ml-2 text-[11px]" style={{ color: 'var(--color-text-faint)' }}>
                            default
                          </span>
                        )}
                      </p>
                      <p
                        className="truncate text-xs"
                        style={{ color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)' }}
                      >
                        {voice.id}
                        {voice.grade && ` · grade ${voice.grade}`}
                      </p>
                    </div>

                    {blocked ? (
                      <span
                        data-testid={`needs-${voice.id}`}
                        className="text-xs"
                        style={{ color: 'var(--color-text-muted)' }}
                      >
                        needs {voice.requires}
                      </span>
                    ) : active ? (
                      <span
                        className="flex items-center gap-1 text-xs"
                        style={{ color: 'var(--color-cyan-light)' }}
                      >
                        <Check size={13} aria-hidden /> speaking
                      </span>
                    ) : (
                      <button
                        type="button"
                        data-testid={`choose-${voice.id}`}
                        disabled={fetching !== null}
                        onClick={() => void choose(voice)}
                        className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs disabled:opacity-40"
                        style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                      >
                        {busy ? (
                          <Loader2 size={13} className="animate-spin" aria-hidden />
                        ) : voice.installed ? (
                          <Check size={13} aria-hidden />
                        ) : (
                          <Download size={13} aria-hidden />
                        )}
                        {busy ? 'Downloading' : voice.installed ? 'Use' : `Download ${size(voice.sizeBytes)}`}
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>

      {loaded && groups.length === 0 && (
        <p data-testid="no-matching-voices" className="py-6 text-center text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Nothing matches “{query}”.
        </p>
      )}

      <p className="mt-3 text-xs" style={{ color: 'var(--color-text-faint)' }}>
        {/* Said once, and where it is read: why a download appears here at all. */}
        Each voice is a separate small file, fetched from huggingface.co only when you ask and recorded
        in Activity. Grades are the pack author’s rating of how well each voice was trained.
        {generated && ` List from ${generated}.`}
      </p>
    </div>
  );
}
