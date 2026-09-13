/**
 * The app Zaram started, and what it saw when it looked.
 *
 * Two shapes on one card, because they are one story: `start_app` produced a
 * URL, `look_at_app` produced a picture of it. Both are never folded — a
 * running process on the person's machine and a screenshot of their page are
 * the two outputs of an agentic reply that must not sit behind a chevron.
 *
 * **Stop is the person's.** A dev server Zaram started is a process on the
 * machine, and the button ends it through `POST /projects/{id}/app/stop` —
 * the same shape as Revert on a change: mutative, by a person, reachable from
 * no tool. The screenshot is served from Zaram's own data directory by name;
 * nothing in the URL is the model's.
 */
import { useState } from 'react';
import { ExternalLink, Square } from 'lucide-react';
import type { ChatToolCall } from '../../stores/chatStore';
import { useChatStore } from '../../stores/chatStore';
import { useProjectStore } from '../../stores/projectStore';

const API = import.meta.env.VITE_ZARAM_API ?? '';

export default function AppCard({ call }: { call: ChatToolCall }) {
  const projectId = useChatStore((s) => s.projectId);
  const stopApp = useProjectStore((s) => s.stopApp);
  const [phase, setPhase] = useState<'idle' | 'working' | 'stopped' | 'failed'>('idle');

  const image = call.image ? call.image.replace(/\\/g, '/').split('/').pop() : '';
  const src = projectId && image ? `${API}/projects/${encodeURIComponent(projectId)}/screens/${encodeURIComponent(image)}` : '';

  async function stop() {
    if (!projectId) return;
    setPhase('working');
    const ok = await stopApp(projectId);
    setPhase(ok ? 'stopped' : 'failed');
  }

  return (
    <div
      className="mt-2 rounded-lg"
      style={{ border: '1px solid var(--color-border-subtle)', background: 'var(--color-glass)' }}
      data-testid="app-card"
    >
      {call.appUrl && (
        <div className="flex items-center gap-2 px-3 py-1.5 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
          <span>{phase === 'stopped' ? 'stopped' : 'running at'}</span>
          <a
            href={call.appUrl}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1"
            style={{ color: 'var(--color-cyan-light)', fontFamily: 'var(--font-mono)' }}
            data-testid="app-url"
          >
            {call.appUrl}
            <ExternalLink size={10} aria-hidden />
          </a>
          <span className="flex-1" />
          {phase !== 'stopped' && projectId && (
            <button
              type="button"
              onClick={() => void stop()}
              disabled={phase === 'working'}
              className="flex items-center gap-1 disabled:opacity-50"
              style={{ color: 'var(--color-amber, #d97706)' }}
              data-testid="app-stop"
            >
              <Square size={10} aria-hidden />
              {phase === 'working' ? 'Stopping…' : phase === 'failed' ? 'Could not stop' : 'Stop'}
            </button>
          )}
        </div>
      )}
      {src && (
        <div className="px-3 py-2">
          <p className="mb-1 text-[10px]" style={{ color: 'var(--color-text-faint)' }}>
            what Zaram saw{call.target ? ` at ${call.target}` : ''}
          </p>
          <img
            src={src}
            alt="Screenshot of the running app"
            style={{ maxWidth: '100%', borderRadius: 6, border: '1px solid var(--color-border-subtle)' }}
            data-testid="app-screenshot"
          />
        </div>
      )}
    </div>
  );
}
