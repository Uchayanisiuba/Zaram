import { FileText } from 'lucide-react'

/**
 * Work — where output lives.
 *
 * It exists because a navigation made only of Memory, Knowledge and Activity is
 * entirely about the system and holds nothing the user made. Memory matters
 * because it is memory *of work*.
 *
 * This is the node, not yet the surface. It holds nothing today because nothing
 * generates artifacts yet — the generative pipeline is a later milestone, and
 * the artifact model it produces is what this surface will list. Rendering a
 * grid of invented rows here would be the "status indicator over hardcoded
 * data" that CLAUDE.md rules out: it would look finished and mean nothing.
 *
 * So: a designed empty state that says what will appear and how to cause it.
 */
export default function WorkWorkspace() {
  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '48px',
      }}
    >
      <div style={{ maxWidth: 420, textAlign: 'center' }}>
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: 12,
            margin: '0 auto 20px',
            display: 'grid',
            placeItems: 'center',
            background: 'rgba(255,255,255,0.04)',
            border: '0.5px solid rgba(255,255,255,0.08)',
            color: '#6B7280',
          }}
        >
          <FileText size={26} />
        </div>

        <h2
          style={{
            font: '500 20px/1.3 var(--font-display, inherit)',
            color: '#F2F4F8',
            margin: '0 0 10px',
          }}
        >
          Nothing here yet
        </h2>

        <p style={{ font: '400 14px/1.6 inherit', color: '#9BA1AC', margin: '0 0 22px' }}>
          Documents, spreadsheets and charts you make will appear here — each
          with the conversation that produced it and the sources it drew on.
        </p>

        {/* The recovery action. An empty state without one is a dead end. */}
        <p
          style={{
            font: '400 12px/1.5 var(--font-mono, ui-monospace, monospace)',
            color: '#6B7280',
            margin: 0,
          }}
        >
          Ask a question in the conversation, then say
          <br />
          &ldquo;write that up as a proposal&rdquo;.
        </p>
      </div>
    </div>
  )
}
