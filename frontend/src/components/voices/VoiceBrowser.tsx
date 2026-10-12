/**
 * Choosing a voice from the active TTS provider.
 *
 * The voice list now comes from the active provider's `available_voices()`,
 * not just the Kokoro manifest. This makes the browser tier-aware:
 * - Tier 4 (Kokoro): 54 voices from local manifest + cache
 * - Tier 1 (Breeze): Cloud voices from API
 * - Tier 2 (Chatterbox): Local GPU voices
 * - Tier 3 (Qwen3): CPU GGUF voices
 *
 * Hardware eligibility from `/voice/tier` drives recommendations and
 * disables incompatible tiers/voices.
 *
 * Three states per voice:
 * * Available — pick it
 * * Not eligible for current tier — greyed with reason
 * * Needs extra — greyed with what it needs
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, Download, Loader2, Play, Search, Zap, Trash2, AlertTriangle, Star, Info } from 'lucide-react';

import {
  downloadVoice,
  fetchActiveVoiceCatalogue,
  fetchTierStatus,
  fetchHardwareProfile,
  cleanupVoiceCache,
  type ActiveVoiceEntry,
  type TierStatus,
  type HardwareProfile,
} from '@/services/characterClient';
import { useSpeechStore } from '@/stores/speechStore';

/** What a voice says when it is tried. Short, and about the product rather than a pangram:
 *  a voice is judged on how it reads ordinary sentences with a few names in them. */
const SAMPLE = 'Hello, this is how I sound. I can read your documents, remember what you decide, and help you get things done.';

/** "0.5 MB" -- the price on a download button, because on metered data it is the half
 *  of the decision that matters. */
function megabytes(bytes: number): string {
  return bytes > 0 ? `${Math.max(0.1, bytes / 1048576).toFixed(1)} MB` : '';
}

interface Props {
  /** The voice that currently speaks; empty means the shipped default. */
  selected: string;
  /** Called with a voice id that is on this machine. */
  onSelect: (id: string) => void;
  /** Whether auto-tier selection is enabled. */
  autoTierEnabled?: boolean;
}

function tierLabel(tier: string): string {
  const labels: Record<string, string> = {
    'TIER_1_BREEZE': 'Tier 1: Breeze TTS 2 (Cloud Premium)',
    'TIER_2_CHATTERBOX': 'Tier 2: Chatterbox Turbo (GPU Efficient)',
    'TIER_3_QWEN3': 'Tier 3: Qwen3-TTS (CPU Lightweight)',
    'TIER_4_KOKORO': 'Tier 4: Kokoro 82M (Fallback)',
  };
  return labels[tier] || tier;
}

function tierShortLabel(tier: string): string {
  const labels: Record<string, string> = {
    'TIER_1_BREEZE': 'Breeze',
    'TIER_2_CHATTERBOX': 'Chatterbox',
    'TIER_3_QWEN3': 'Qwen3',
    'TIER_4_KOKORO': 'Kokoro',
  };
  return labels[tier] || tier;
}

function tierColor(tier: string): string {
  const colors: Record<string, string> = {
    'TIER_1_BREEZE': 'var(--color-purple)',
    'TIER_2_CHATTERBOX': 'var(--color-cyan)',
    'TIER_3_QWEN3': 'var(--color-green)',
    'TIER_4_KOKORO': 'var(--color-amber)',
  };
  return colors[tier] || 'var(--color-text-muted)';
}

export default function VoiceBrowser({
  selected,
  onSelect,
  autoTierEnabled,
}: Props) {
  const [voices, setVoices] = useState<ActiveVoiceEntry[]>([]);
  const [activeProvider, setActiveProvider] = useState<string | null>(null);
  const [activeTier, setActiveTier] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [query, setQuery] = useState('');
  const [fetching, setFetching] = useState<string | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [failure, setFailure] = useState('');
  const [tierStatus, setTierStatus] = useState<TierStatus | null>(null);
  const [hardwareProfile, setHardwareProfile] = useState<HardwareProfile | null>(null);
  const [recommendedTier, setRecommendedTier] = useState<string | null>(null);
  const [cleaningUp, setCleaningUp] = useState(false);
  const [cleanupReport, setCleanupReport] = useState<{ deleted: number; freedMB: number } | null>(null);

  const load = useCallback(async () => {
    const [catalogue, tier, hardware] = await Promise.all([
      fetchActiveVoiceCatalogue(),
      fetchTierStatus(),
      fetchHardwareProfile(),
    ]);
    setVoices(catalogue.voices);
    setActiveProvider(catalogue.provider);
    setActiveTier(catalogue.activeTier);
    setTierStatus(tier);
    setHardwareProfile(hardware);

    // Determine recommended tier from hardware eligibility
    if (tier.tier_status) {
      const tierOrder = ['TIER_1_BREEZE', 'TIER_2_CHATTERBOX', 'TIER_3_QWEN3', 'TIER_4_KOKORO'];
      for (const tierKey of tierOrder) {
        if (tier.tier_status[tierKey]?.eligible) {
          setRecommendedTier(tierKey);
          break;
        }
      }
    }

    setLoaded(true);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  /** Fetch one voice and nothing else: it is not chosen, so a person can build up a
   *  shelf of voices and try them before deciding which one speaks. */
  async function download(voice: ActiveVoiceEntry): Promise<boolean> {
    setFailure('');
    setFetching(voice.id);
    try {
      await downloadVoice(voice.id);
      await load();
      return true;
    } catch (error) {
      setFailure(error instanceof Error ? error.message : 'That voice could not be fetched.');
      return false;
    } finally {
      setFetching(null);
    }
  }

  /** Play a sample in this voice and change nothing: not the voice that speaks, not
   *  a setting. Offered only for a voice already on the machine, so trying one is
   *  never a download nobody asked for. */
  async function test(voice: ActiveVoiceEntry) {
    setFailure('');
    setTesting(voice.id);
    try {
      await useSpeechStore.getState().speak(SAMPLE, voice.id);
      const reason = useSpeechStore.getState().error;
      if (reason) setFailure(reason);
    } catch (error) {
      setFailure(error instanceof Error ? error.message : 'That voice could not be played.');
    } finally {
      setTesting(null);
    }
  }

  async function choose(voice: ActiveVoiceEntry) {
    setFailure('');
    // A voice that is not here is fetched first, and is not chosen if the fetch failed:
    // otherwise Settings would name a voice that cannot speak.
    if (voice.installed === false && !(await download(voice))) return;
    onSelect(voice.id);
  }

  async function handleCleanup() {
    setCleaningUp(true);
    setFailure('');
    try {
      // Empty: the backend keeps the voice that speaks now.
      const report = await cleanupVoiceCache('', false);
      setCleanupReport({ deleted: report.deleted_count, freedMB: report.freed_mb });
      await load();
    } catch (error) {
      setFailure(error instanceof Error ? error.message : 'Cleanup failed.');
    } finally {
      setCleaningUp(false);
    }
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
    const byLanguage = new Map<string, ActiveVoiceEntry[]>();
    for (const voice of shown) {
      const list = byLanguage.get(voice.language) ?? [];
      list.push(voice);
      byLanguage.set(voice.language, list);
    }
    return [...byLanguage.entries()];
  }, [voices, query]);

  const tierOrder = ['TIER_1_BREEZE', 'TIER_2_CHATTERBOX', 'TIER_3_QWEN3', 'TIER_4_KOKORO'];
  // Said in words rather than left to a tooltip: a greyed chip with its reason on hover
  // reads as "there are other voice engines and they are missing".
  const unbuilt = tierOrder.filter((key) => (tierStatus?.tier_status as Record<string, { implemented?: boolean }> | undefined)?.[key]?.implemented === false);

  if (loaded && voices.length === 0 && activeProvider) {
    return (
      <p data-testid="no-voices" className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
        No voices available from {activeProvider}. The voice that is speaking now still works.
      </p>
    );
  }

  return (
    <div data-testid="voice-browser" className="w-full">
      {/* Tier Status Header */}
      <div className="mb-4 p-3 rounded-lg" style={{ background: 'var(--color-glass)', border: '1px solid var(--color-border)' }}>
        <div className="flex items-center gap-3 mb-2">
          <Zap size={18} style={{ color: 'var(--color-text-faint)' }} aria-hidden />
          <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
            Speech engines
          </span>
          {/* "AUTO" only when automatic choice is really running. This read a prop
              nobody passed, so it said AUTO always -- with one engine built and nothing
              to choose between. */}
          {(autoTierEnabled ?? tierStatus?.auto_tier_enabled) === true && (
            <span className="ml-auto text-[10px] px-2 py-0.5 rounded" style={{ background: 'var(--color-green)', color: 'var(--color-bg)' }}>
              AUTO
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {tierStatus?.tier_status && tierOrder.map((tierKey) => {
            const status = tierStatus.tier_status[tierKey];
            const isActive = tierKey === tierStatus.active_tier;
            const isRecommended = tierKey === recommendedTier;
            const isEligible = status?.eligible ?? false;
            return (
              <span
                key={tierKey}
                className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium"
                style={{
                  background: isEligible ? `${tierColor(tierKey)}20` : 'var(--color-glass)',
                  color: isEligible ? tierColor(tierKey) : 'var(--color-text-faint)',
                  border: isActive ? `1px solid ${tierColor(tierKey)}` : isEligible ? '1px solid transparent' : '1px dashed var(--color-border)',
                  opacity: isEligible ? 1 : 0.6,
                }}
                title={isEligible ? (isRecommended ? 'Recommended for your hardware' : 'Compatible') : status?.reason || 'Not eligible for your hardware'}
              >
                {isActive && <span className="text-[8px]">● </span>}
                {isRecommended && (
                  <span title="Recommended for your hardware">
                    <Star size={9} className="text-[8px]" aria-label="Recommended" />
                  </span>
                )}
                {tierShortLabel(tierKey)}
                {!isEligible && <AlertTriangle size={9} aria-label="Not eligible" />}
              </span>
            );
          })}
        </div>
        {unbuilt.length > 0 && (
          <p data-testid="engines-not-built" className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Kokoro is the only speech engine that works today. {unbuilt.map(tierShortLabel).join(', ')}{' '}
            {unbuilt.length === 1 ? 'is' : 'are'} not built yet, so {unbuilt.length === 1 ? 'it has' : 'they have'} no voices to
            list. The voices below are Kokoro&apos;s.
          </p>
        )}
        {activeTier && (
          <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Active: <strong style={{ color: tierColor(activeTier) }}>{tierLabel(activeTier)}</strong>
            {tierStatus?.fallback_tier && (
              <> • Fallback: <strong style={{ color: tierColor(tierStatus.fallback_tier) }}>{tierLabel(tierStatus.fallback_tier)}</strong></>
            )}
            {recommendedTier && recommendedTier !== activeTier && (
              <Info size={11} className="inline ml-1" aria-label="Recommended tier available" style={{ color: 'var(--color-cyan)', verticalAlign: 'middle' }} />
            )}
          </p>
        )}
      </div>

      {/* Hardware Profile Summary */}
      {hardwareProfile && (
        <details className="mb-4">
          <summary className="text-xs cursor-pointer" style={{ color: 'var(--color-text-muted)' }}>
            Hardware Profile (for tier routing)
          </summary>
          <div className="mt-2 p-2 text-[10px] font-mono" style={{ background: 'var(--color-glass)', border: '1px solid var(--color-border)', borderRadius: '4px' }}>
            <div>GPU: {hardwareProfile.gpu_name} ({hardwareProfile.gpu_vendor})</div>
            {hardwareProfile.total_vram_gb !== null && <div>VRAM: {hardwareProfile.total_vram_gb} GB total, {hardwareProfile.free_vram_gb ?? '?'} GB free</div>}
            {hardwareProfile.total_system_ram_gb !== null && <div>System RAM: {hardwareProfile.total_system_ram_gb} GB</div>}
            <div>Cloud LLM: {hardwareProfile.cloud_llm_active ? `Yes (${hardwareProfile.cloud_llm_provider})` : 'No'}</div>
            <div>Local LLM: {hardwareProfile.local_llm_active ? `Yes (${hardwareProfile.local_llm_model_id}, ~${hardwareProfile.local_llm_vram_footprint_gb ?? '?'} GB VRAM)` : 'No'}</div>
          </div>
        </details>
      )}

      {/* Cleanup Section (only for Kokoro) */}
      {activeProvider === 'kokoro' && (
        <div className="mb-4 p-3 rounded-lg" style={{ background: 'var(--color-glass)', border: '1px solid var(--color-border)' }}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Trash2 size={16} style={{ color: 'var(--color-text-faint)' }} aria-hidden />
              <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
                Local Voice Cleanup
              </span>
            </div>
            <button
              type="button"
              onClick={handleCleanup}
              disabled={cleaningUp}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs disabled:opacity-40"
              style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
            >
              {cleaningUp ? <Loader2 size={13} className="animate-spin" aria-hidden /> : <Trash2 size={13} aria-hidden />}
              {cleaningUp ? 'Cleaning...' : 'Remove Unused Voices'}
            </button>
          </div>
          <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Deletes the downloaded Kokoro voices you are not using, keeping the one that speaks now, to reclaim disk space.
            {cleanupReport && (
              <> <strong>Last run:</strong> removed {cleanupReport.deleted} files, freed {cleanupReport.freedMB} MB.</>
            )}
          </p>
        </div>
      )}

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
                const blocked = !voice.available;
                // An empty `selected` means the shipped default is the one speaking.
                const active = selected ? selected === voice.id : voice.default;
                const busy = fetching === voice.id;
                const isEligible = voice.available;
                return (
                  <li
                    key={voice.id}
                    data-testid={`voice-${voice.id}`}
                    className="flex items-center gap-3 rounded-lg px-3 py-2"
                    style={{
                      background: 'var(--color-glass)',
                      border: `1px solid ${active ? 'var(--color-cyan)' : (isEligible ? 'var(--color-border-subtle)' : 'var(--color-border)')}`,
                      opacity: isEligible ? 1 : 0.5,
                    }}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm" style={{ color: 'var(--color-text)' }}>
                        {voice.name}
                        <span className="ml-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                          {voice.gender}
                        </span>
                        {active && (
                          <span className="ml-2 text-[11px]" style={{ color: 'var(--color-cyan)' }}>
                            speaking
                          </span>
                        )}
                      </p>
                      <p
                        className="truncate text-xs"
                        style={{ color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)' }}
                      >
                        {voice.id}
                        {voice.grade && ` · grade ${voice.grade}`}
                        <span className="ml-2 text-[10px]" style={{ color: tierColor(activeTier || '') }}>
                          [{voice.provider}]
                        </span>
                      </p>
                    </div>

                    {blocked ? (
                      <span
                        data-testid={`unavailable-${voice.id}`}
                        className="text-xs"
                        style={{ color: 'var(--color-text-muted)' }}
                        title="Not available from current provider"
                      >
                        unavailable ({voice.provider}){voice.requires ? ` · needs ${voice.requires}` : ''}
                      </span>
                    ) : voice.installed === false ? (
                      <button
                        type="button"
                        data-testid={`download-${voice.id}`}
                        disabled={fetching !== null}
                        onClick={() => void download(voice)}
                        title="Fetches this one voice from huggingface.co. Zaram asks first, and the request is logged."
                        className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs disabled:opacity-40"
                        style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                      >
                        {busy ? (
                          <Loader2 size={13} className="animate-spin" aria-hidden />
                        ) : (
                          <Download size={13} aria-hidden />
                        )}
                        Download{megabytes(voice.sizeBytes) ? ` · ${megabytes(voice.sizeBytes)}` : ''}
                      </button>
                    ) : (
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          data-testid={`test-${voice.id}`}
                          disabled={testing !== null || fetching !== null}
                          onClick={() => void test(voice)}
                          title="Plays a short sample in this voice. Nothing is changed."
                          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs disabled:opacity-40"
                          style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                        >
                          {testing === voice.id ? (
                            <Loader2 size={13} className="animate-spin" aria-hidden />
                          ) : (
                            <Play size={13} aria-hidden />
                          )}
                          Test
                        </button>
                        {active ? (
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
                            <Check size={13} aria-hidden />
                            Use
                          </button>
                        )}
                      </div>
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
          Nothing matches "{query}".
        </p>
      )}

      <p className="mt-3 text-xs" style={{ color: 'var(--color-text-faint)' }}>
        Voices from <strong>{activeProvider || 'active provider'}</strong> ({activeTier ? tierLabel(activeTier) : 'unknown tier'}).
        {recommendedTier && recommendedTier !== activeTier && (
          <> <br /> Recommended for your hardware: <strong>{tierLabel(recommendedTier)}</strong>.</>
        )}
      </p>
    </div>
  );
}