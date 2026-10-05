import { usePageCheckStore, replyKey, MAX_AUTO_FIXES } from '@/stores/pageCheckStore';

/**
 * What running the page before showing it found, said under the reply.
 *
 * Every outcome is a sentence, including the ones that are not good news --
 * "could not be checked" is shown as that and not as silence, because a page
 * that was never run must not look like a page that passed. Only `checking` and
 * `fixing` are transient; the rest stay with the reply.
 */
export default function PageCheckLine({ reply }: { reply: string }) {
  const state = usePageCheckStore((s) => s.byReply[replyKey(reply)]);
  const setEnabled = usePageCheckStore((s) => s.setEnabled);
  if (!state) return null;

  let text: string;
  switch (state.status) {
    case 'checking':
      text = 'Running the page to check it…';
      break;
    case 'clean':
      text = state.slowSeconds
        ? `Ran without errors, but it held still for ${state.slowSeconds.toFixed(1)} seconds while it started (measured without a graphics card, so likely shorter on yours).`
        : 'Ran without errors.';
      break;
    case 'fixing':
      text = `It did not run: ${state.note} Asked for a fix (try ${state.attempt} of ${MAX_AUTO_FIXES}).`;
      break;
    case 'failed':
      text = `It did not run: ${state.note} Preview it to see, or use Fix this.`;
      break;
    case 'gave-up':
      text = `Still not running after ${MAX_AUTO_FIXES} fixes: ${state.note} Preview it to see, or use Fix this.`;
      break;
    default:
      text = `Not checked: ${state.note || 'it could not be run'}.`;
  }

  return (
    <p
      role="status"
      data-testid="page-check"
      data-status={state.status}
      className="mt-1 w-full text-xs"
      style={{ color: 'var(--color-text-muted)', margin: '4px 0 0' }}
    >
      {text}{' '}
      <button
        type="button"
        onClick={() => setEnabled(false)}
        className="underline underline-offset-2"
        title="Stop running pages before showing them. Turn it back on beside the Thinking switch."
      >
        Turn off
      </button>
    </p>
  );
}
