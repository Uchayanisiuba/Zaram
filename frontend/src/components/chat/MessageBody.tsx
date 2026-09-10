import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ReactNode } from 'react';

/**
 * A reply, rendered as the markdown it already is.
 *
 * Until 10 September 2026 this was one line — `whitespace-pre-wrap` around the
 * raw string — so a table arrived as a wall of pipes, a heading as literal
 * hashes, and emphasis as asterisks. No model can fix that: every one of them
 * emits correct markdown and Zaram was discarding it at the last step. It is
 * the single largest gap between how a reply reads here and how the same reply
 * reads in any other assistant, and it is a rendering problem rather than an
 * intelligence one.
 *
 * **Raw HTML stays off**, which is `react-markdown`'s default and is why no
 * `rehype-raw` appears below. Recall folds passages into replies and those
 * passages are written by whoever sent the user the file; `core/untrusted.py`
 * exists because of it. Executing that text in the app's own origin is the
 * injection surface the whole untrusted-content rule is drawn around. Every
 * other assistant makes the same call for the same reason — rich content goes
 * in a sandboxed container, never in the message body — and Zaram already has
 * that container in `ArtifactPreview` and `CodePreviewPanel`.
 */

/** Muted, bordered, and never violet — that token means cloud. */
const RULE = '1px solid var(--color-border)';

function Fence({ children }: { children?: ReactNode }) {
  return (
    <pre
      style={{
        margin: '8px 0',
        padding: '10px 12px',
        borderRadius: 8,
        border: RULE,
        background: 'var(--color-glass)',
        overflowX: 'auto',
        fontSize: 12,
        lineHeight: 1.5,
      }}
    >
      {children}
    </pre>
  );
}

export default function MessageBody({ text }: { text: string }) {
  return (
    <div className="zaram-md text-sm leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          /**
           * A link is text here, not a control.
           *
           * `electron/main.js` hardens the window: `setWindowOpenHandler`
           * denies every `window.open` and `will-navigate` cancels anything
           * leaving the app. An anchor would therefore look like a link,
           * invite a click, and do nothing at all — which the UI principles
           * forbid in as many words: disabled capabilities are visible, not
           * silent.
           *
           * So the destination is shown instead of hidden behind it. On a
           * product whose replies quote documents written by strangers, being
           * able to *read* where a link points without following it is the
           * better behaviour anyway, not a consolation for the missing one.
           */
          a: ({ href, children }) => (
            <span>
              {children}
              {href && (
                <span
                  style={{ color: 'var(--color-text-muted)', wordBreak: 'break-all' }}
                >
                  {' '}
                  ({href})
                </span>
              )}
            </span>
          ),

          /**
           * Tables scroll inside their own box.
           *
           * A wide table must never make the conversation itself scroll
           * sideways — the reply column is a fixed measure and the surface
           * around it is not a spreadsheet.
           */
          table: ({ children }) => (
            <div style={{ overflowX: 'auto', margin: '8px 0' }}>
              <table
                style={{
                  borderCollapse: 'collapse',
                  fontSize: 12,
                  minWidth: '100%',
                }}
              >
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th
              style={{
                border: RULE,
                padding: '6px 10px',
                textAlign: 'left',
                fontWeight: 600,
                background: 'var(--color-glass)',
              }}
            >
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td style={{ border: RULE, padding: '6px 10px', verticalAlign: 'top' }}>
              {children}
            </td>
          ),

          pre: ({ children }) => <Fence>{children}</Fence>,
          code: ({ className, children, ...rest }) => {
            // `react-markdown` gives a fenced block a `language-*` class and an
            // inline span none. Distinguishing on that rather than on a prop
            // is what the library actually guarantees across versions.
            const fenced = typeof className === 'string' && className.startsWith('language-');
            if (fenced) {
              return (
                <code className={className} {...rest}>
                  {children}
                </code>
              );
            }
            return (
              <code
                style={{
                  padding: '1px 5px',
                  borderRadius: 4,
                  border: RULE,
                  background: 'var(--color-glass)',
                  fontSize: '0.92em',
                }}
                {...rest}
              >
                {children}
              </code>
            );
          },

          // Headings inside a reply are not page headings. They step down one
          // level from where the surface already is, so a model writing `#`
          // cannot out-shout the interface around it.
          h1: ({ children }) => <h3 style={{ fontSize: 15, fontWeight: 600, margin: '12px 0 4px' }}>{children}</h3>,
          h2: ({ children }) => <h4 style={{ fontSize: 14, fontWeight: 600, margin: '10px 0 4px' }}>{children}</h4>,
          h3: ({ children }) => <h5 style={{ fontSize: 13, fontWeight: 600, margin: '10px 0 4px' }}>{children}</h5>,
          h4: ({ children }) => <h6 style={{ fontSize: 13, fontWeight: 600, margin: '8px 0 4px' }}>{children}</h6>,

          p: ({ children }) => <p style={{ margin: '0 0 8px' }}>{children}</p>,
          ul: ({ children }) => <ul style={{ margin: '0 0 8px', paddingLeft: 20, listStyle: 'disc' }}>{children}</ul>,
          ol: ({ children }) => <ol style={{ margin: '0 0 8px', paddingLeft: 20, listStyle: 'decimal' }}>{children}</ol>,
          li: ({ children }) => <li style={{ margin: '2px 0' }}>{children}</li>,
          blockquote: ({ children }) => (
            <blockquote
              style={{
                margin: '8px 0',
                paddingLeft: 10,
                borderLeft: '2px solid var(--color-border)',
                color: 'var(--color-text-muted)',
              }}
            >
              {children}
            </blockquote>
          ),
          hr: () => <hr style={{ border: 0, borderTop: RULE, margin: '12px 0' }} />,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
