/**
 * What one step produced, in a pane of its own.
 *
 * Asked for on 12 September 2026 against Claude Code, where a finished step
 * opens to show its output in a bounded box with its own scrollbar: the wheel
 * scrolls the output while the pointer is over it, and the transcript around
 * it stays put. That is the whole interaction, and it is what makes a step
 * list readable — a run that read four files is four short rows, and any one
 * of them can be checked without the other three unrolling.
 *
 * **Text, never markup.** The output is a file's contents or a search hit,
 * written by whoever wrote the file: third-party text under `core/untrusted`,
 * bounded by `output_excerpt` on the way out and rendered into a `<pre>` here.
 * Nothing in it can become an element.
 *
 * Bounded in height rather than lines, because a line of minified JSON is one
 * line and a screen tall. `overscroll-behavior: contain` keeps a wheel that
 * reaches the pane's end from throwing the conversation behind it — the
 * transcript is what the user was reading, and a scroll they did not ask for
 * is the one motion that reads as the product misbehaving.
 */
export default function StepOutput({ text }: { text: string }) {
  if (!text) return null;
  return (
    <pre
      className="mt-1 rounded-md text-[10.5px] leading-snug"
      style={{
        fontFamily: 'var(--font-mono)',
        color: 'var(--color-text-muted)',
        background: 'var(--color-glass)',
        border: '1px solid var(--color-border-subtle)',
        padding: '6px 8px',
        margin: '4px 0 0',
        maxHeight: 240,
        overflow: 'auto',
        overscrollBehavior: 'contain',
        whiteSpace: 'pre',
      }}
      data-testid="step-output"
    >
      {text}
    </pre>
  );
}
