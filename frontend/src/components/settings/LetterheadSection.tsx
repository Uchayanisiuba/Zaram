/**
 * Where a user puts their own name and mark on the documents Zaram generates.
 *
 * **This is the way in that was missing, not a new capability.** The backend
 * has validated logos, embedded them as `data:` URIs and rendered them into a
 * masthead for weeks; nothing anywhere could supply one, so every document
 * generated went out unbranded. `artifacts/letterhead.py`'s own first line says
 * what that costs: *"an invoice with no letterhead is a draft."*
 *
 * **Settings is where it is visible and editable — never the only way in.**
 * `docs/MILESTONES.md` settled the shape: a letterhead is captured *in chat*,
 * by dropping a logo in the composer, and offered at the moment a document is
 * first generated without one. Rule 7e is explicit that asking someone to fill
 * a form before their first document is the wrong order. This surface is the
 * afterwards.
 *
 * It lives in its own file because `SettingsWorkspace` is already 1,486 lines,
 * and takes `Row`/`Section` as props rather than importing them, so the two
 * files do not import each other in a circle.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  adoptTemplate,
  clearLogo,
  fetchLetterhead,
  fetchLetterheadLogo,
  readTemplate,
  saveLetterhead,
  uploadLogo,
  type Letterhead,
  type TemplateProposal,
} from '../../services/letterheadClient';

/** How many address lines the control offers. Matches `MAX_LINES` in the
 *  store, which is the authority; going over is refused there rather than
 *  being silently truncated here. */
const LINE_SLOTS = 4;

export interface LetterheadSectionProps {
  /** `Row` from `SettingsWorkspace`, passed in so this file does not import
   *  from the workspace that renders it. */
  Row: React.ComponentType<{
    label: string;
    value?: string;
    detail?: React.ReactNode;
    state?: 'good' | 'neutral' | 'absent' | 'warn';
    children?: React.ReactNode;
  }>;
}

/**
 * One extracted field, editable, with the line it came from underneath.
 *
 * The evidence is what makes this a review rather than a form. Confirming
 * "yes, that is my address" is a far easier question than "what is your
 * address" — but only when the source line is in view.
 */
function ProposedRow({
  label,
  evidence,
  value,
  onChange,
}: {
  label: string;
  evidence: string;
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <div className="flex flex-col items-end gap-0.5 w-full">
      <div className="flex items-center gap-2">
        {label && (
          <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
            {label}
          </span>
        )}
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-label={label || 'Proposed line'}
          maxLength={120}
          className="w-56 px-2 py-1 text-xs rounded-lg bg-transparent outline-none"
          style={{ border: '1px solid var(--color-border-subtle)', color: 'var(--color-text)' }}
        />
      </div>
      {evidence && (
        <span
          className="text-[10px] pr-1"
          style={{ color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)' }}
        >
          read from: {evidence}
        </span>
      )}
    </div>
  );
}

export default function LetterheadSection({ Row }: LetterheadSectionProps) {
  const [letterhead, setLetterhead] = useState<Letterhead | null>(null);
  const [logo, setLogo] = useState<string>('');
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [nameDraft, setNameDraft] = useState<string | null>(null);
  const [linesDraft, setLinesDraft] = useState<string[] | null>(null);
  const filePicker = useRef<HTMLInputElement>(null);
  const templatePicker = useRef<HTMLInputElement>(null);
  // The review. Non-null means a document has been read and nothing has been
  // applied — the gap between those two is the whole point of the feature.
  const [proposal, setProposal] = useState<TemplateProposal | null>(null);
  const [confirmed, setConfirmed] = useState<{ name: string; lines: string[]; logo: string }>({
    name: '',
    lines: [],
    logo: '',
  });

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const current = await fetchLetterhead(controller.signal);
        setLetterhead(current);
        // Only fetch the pixels when there are some. The stored URI can be
        // most of a megabyte and there is no reason to move it to draw the
        // word "Add".
        if (current.hasLogo) setLogo(await fetchLetterheadLogo(controller.signal));
      } catch {
        // Left null, which renders "unavailable" rather than an empty form.
        // A form that looks editable and saves nothing is worse than an
        // honest absence.
      }
    })();
    return () => controller.abort();
  }, []);

  const run = useCallback(async (key: string, work: () => Promise<void>) => {
    setBusy(key);
    setProblem(null);
    try {
      await work();
    } catch (error) {
      // The backend's sentence, unchanged. It says which formats are accepted,
      // what the limit is, and why SVG is refused — none of which this
      // component knows, and all of which the user needs.
      setProblem(error instanceof Error ? error.message : 'That did not work.');
    } finally {
      setBusy(null);
    }
  }, []);

  if (letterhead === null) {
    return (
      <Row
        label="Letterhead"
        value="unavailable"
        state="absent"
        detail="Zaram could not read your letterhead from the backend. Nothing is shown rather than an empty form, which would look editable and save nothing."
      />
    );
  }

  const lines = linesDraft ?? letterhead.lines;
  const padded = [...lines, ...Array(Math.max(0, LINE_SLOTS - lines.length)).fill('')].slice(
    0,
    LINE_SLOTS,
  );

  return (
    <>
      <Row
        label="Business name"
        value={letterhead.name || 'not set'}
        state={letterhead.name ? 'good' : 'neutral'}
        detail={
          'Set in bold at the top of every document you generate. Leave it empty and documents ' +
          'still come out titled and ruled — the absence of branding never reads as a rendering fault.'
        }
      >
        <div className="flex items-center gap-2">
          <input
            value={nameDraft ?? letterhead.name}
            onChange={(e) => setNameDraft(e.target.value)}
            placeholder="Northwind Studio"
            aria-label="Your business name"
            maxLength={120}
            className="w-44 px-2 py-1 text-xs rounded-lg bg-transparent outline-none"
            style={{ border: '1px solid var(--color-border-subtle)', color: 'var(--color-text)' }}
          />
          <button
            disabled={busy === 'name' || nameDraft === null}
            onClick={() =>
              void run('name', async () => {
                // The stored value comes back, not the typed one: the store
                // collapses whitespace and bounds length.
                setLetterhead(await saveLetterhead({ name: nameDraft ?? '' }));
                setNameDraft(null);
              })
            }
            className="text-[11px] px-2 py-1 rounded-lg disabled:opacity-40"
            style={{ color: 'var(--color-cyan-light)' }}
          >
            {busy === 'name' ? '…' : 'Save'}
          </button>
        </div>
      </Row>

      <Row
        label="Address and contact"
        value={letterhead.lines.length ? `${letterhead.lines.length} lines` : 'not set'}
        state={letterhead.lines.length ? 'good' : 'neutral'}
        detail={
          'Whatever belongs under your name, in the order you write it — address, email, ' +
          'registration number. Zaram does not parse these or decide what a postcode is: an ' +
          'address format that is right in Lagos is wrong in Berlin, so this is your business ' +
          'rather than something to model.'
        }
      >
        <div className="flex flex-col items-end gap-1.5">
          {padded.map((line, index) => (
            <input
              key={index}
              value={line}
              onChange={(e) => {
                const next = [...padded];
                next[index] = e.target.value;
                setLinesDraft(next);
              }}
              placeholder={index === 0 ? '12 Dock Road' : ''}
              aria-label={`Letterhead line ${index + 1}`}
              maxLength={120}
              className="w-56 px-2 py-1 text-xs rounded-lg bg-transparent outline-none"
              style={{ border: '1px solid var(--color-border-subtle)', color: 'var(--color-text)' }}
            />
          ))}
          <button
            disabled={busy === 'lines' || linesDraft === null}
            onClick={() =>
              void run('lines', async () => {
                // Empty slots are dropped by the store, so a user clearing the
                // middle line does not leave a gap in their masthead.
                setLetterhead(await saveLetterhead({ lines: padded.filter((l) => l.trim()) }));
                setLinesDraft(null);
              })
            }
            className="text-[11px] px-2 py-1 rounded-lg disabled:opacity-40"
            style={{ color: 'var(--color-cyan-light)' }}
          >
            {busy === 'lines' ? '…' : 'Save'}
          </button>
        </div>
      </Row>

      <Row
        label="Logo"
        value={letterhead.hasLogo ? `${Math.round(letterhead.logoBytes / 1024)} KB` : 'not set'}
        state={letterhead.hasLogo ? 'good' : 'neutral'}
        detail={
          'PNG, JPEG or WebP, up to 512 KB. A transparent PNG sits on the masthead without a ' +
          'white box around it.\n\n' +
          'The image is embedded in every document rather than linked — a generated file has to ' +
          'render the same on a machine that has never seen this one, and must fetch nothing when ' +
          'it opens. SVG is refused for that second reason: it can reference a file on the ' +
          'internet, and a document Zaram made must not call home from inside a client’s inbox.'
        }
      >
        <div className="flex items-center gap-2">
          {logo && (
            // A checked background so a transparent logo is visible as
            // transparent rather than as whatever the panel happens to be.
            <span
              className="rounded"
              style={{
                padding: 4,
                background:
                  'repeating-conic-gradient(var(--color-border-subtle) 0% 25%, transparent 0% 50%) 50% / 8px 8px',
              }}
            >
              <img src={logo} alt="Your logo" style={{ height: 24, width: 'auto', display: 'block' }} />
            </span>
          )}
          <input
            ref={filePicker}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              // Cleared immediately so choosing the same file twice still
              // fires a change — the ordinary way someone retries after
              // fixing an export.
              e.target.value = '';
              if (!file) return;
              void run('logo', async () => {
                setLetterhead(await uploadLogo(file));
                setLogo(await fetchLetterheadLogo());
              });
            }}
          />
          <button
            disabled={busy === 'logo'}
            onClick={() => filePicker.current?.click()}
            className="text-[11px] px-2 py-1 rounded-lg disabled:opacity-40"
            style={{ color: 'var(--color-cyan-light)' }}
          >
            {busy === 'logo' ? '…' : letterhead.hasLogo ? 'Replace' : 'Add a logo'}
          </button>
          {letterhead.hasLogo && (
            <button
              disabled={busy === 'logo'}
              onClick={() =>
                void run('logo', async () => {
                  setLetterhead(await clearLogo());
                  setLogo('');
                })
              }
              className="text-[11px] px-2 py-1 rounded-lg disabled:opacity-40"
              style={{ color: 'var(--color-text-muted)' }}
            >
              Remove
            </button>
          )}
        </div>
      </Row>

      <Row
        label="Learn from a document you already send"
        value={proposal ? 'review it' : 'optional'}
        state={proposal ? 'warn' : 'neutral'}
        detail={
          'Upload an invoice or letter you have sent before, in Word or PDF, and Zaram reads ' +
          'your name, address, payment terms and logo out of it.\n\n' +
          'It reads the identity, never the layout. Reproducing an exact layout means ' +
          'reimplementing Word, and the failure mode of trying is the one that hurts: a document ' +
          'ninety per cent in your house style is worse than one plainly Zaram\u2019s, because a ' +
          'client notices the wrong font on something wearing your letterhead.\n\n' +
          'Nothing is applied until you accept it.'
        }
      >
        <div className="flex items-center gap-2">
          <input
            ref={templatePicker}
            type="file"
            accept=".docx,.pdf,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = '';
              if (!file) return;
              void run('template', async () => {
                const read = await readTemplate(file);
                setProposal(read);
                setConfirmed({
                  name: read.name?.value ?? '',
                  lines: read.addressLines.map((line) => line.value),
                  logo: read.logo?.value ?? '',
                });
              });
            }}
          />
          <button
            disabled={busy === 'template'}
            onClick={() => templatePicker.current?.click()}
            className="text-[11px] px-2 py-1 rounded-lg disabled:opacity-40"
            style={{ color: 'var(--color-cyan-light)' }}
          >
            {busy === 'template' ? 'Reading\u2026' : 'Read a document'}
          </button>
        </div>
      </Row>

      {proposal && (
        <Row
          label="What Zaram read"
          state="warn"
          detail={
            'Each line shows what it was read from. Correcting one here is easier than ' +
            'correcting it after a client has seen it \u2014 and what you accept is what gets ' +
            'saved, not what was extracted.'
          }
        >
          <div className="flex flex-col items-end gap-2 w-full">
            <ProposedRow
              label="Name"
              evidence={proposal.name?.evidence ?? ''}
              value={confirmed.name}
              onChange={(name) => setConfirmed((c) => ({ ...c, name }))}
            />
            {confirmed.lines.map((line, index) => (
              <ProposedRow
                key={index}
                label={index === 0 ? 'Address' : ''}
                evidence={proposal.addressLines[index]?.evidence ?? ''}
                value={line}
                onChange={(next) =>
                  setConfirmed((c) => {
                    const lines = [...c.lines];
                    lines[index] = next;
                    return { ...c, lines };
                  })
                }
              />
            ))}

            {confirmed.logo && (
              <div className="flex items-center gap-2 self-end">
                <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                  Logo found
                </span>
                <span
                  className="rounded"
                  style={{
                    padding: 4,
                    background:
                      'repeating-conic-gradient(var(--color-border-subtle) 0% 25%, transparent 0% 50%) 50% / 8px 8px',
                  }}
                >
                  <img
                    src={confirmed.logo}
                    alt="Proposed logo"
                    style={{ height: 24, display: 'block' }}
                  />
                </span>
                <button
                  onClick={() => setConfirmed((c) => ({ ...c, logo: '' }))}
                  className="text-[11px] px-2 py-1 rounded-lg"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  Not my logo
                </button>
              </div>
            )}

            {/* The backend writes these questions, because it is the thing that
                knows which of three absences it found: nothing there, found and
                unusable, or several candidates and none clearly right. */}
            {proposal.missing.map((gap) => (
              <p
                key={gap.name}
                className="text-[11px] leading-relaxed self-start"
                style={{ color: 'var(--color-text-faint)' }}
              >
                {gap.question}
              </p>
            ))}

            {(proposal.termsDays || proposal.currency || proposal.numbering) && (
              // Read and shown, not stored: the letterhead store holds an
              // identity, and terms, currency and numbering belong to the
              // invoice layer. Shown so the review is honest about everything
              // that was read rather than only about what it kept.
              <p
                className="text-[11px] leading-relaxed self-start"
                style={{ color: 'var(--color-text-faint)' }}
              >
                Also read, and not saved yet:{' '}
                {[
                  proposal.termsDays ? proposal.termsDays.value + ' day terms' : '',
                  proposal.currency ? 'currency ' + proposal.currency.value : '',
                  proposal.numbering ? 'numbering ' + proposal.numbering.value : '',
                ]
                  .filter(Boolean)
                  .join(', ')}
                .
              </p>
            )}

            <div className="flex items-center gap-2">
              <button
                onClick={() => setProposal(null)}
                className="text-[11px] px-2 py-1 rounded-lg"
                style={{ color: 'var(--color-text-muted)' }}
              >
                Discard
              </button>
              <button
                disabled={busy === 'adopt'}
                onClick={() =>
                  void run('adopt', async () => {
                    setLetterhead(
                      await adoptTemplate({
                        ...confirmed,
                        lines: confirmed.lines.filter((l) => l.trim()),
                      }),
                    );
                    setLogo(confirmed.logo);
                    setProposal(null);
                  })
                }
                className="text-[11px] px-2 py-1 rounded-lg disabled:opacity-40"
                style={{ color: 'var(--color-cyan-light)' }}
              >
                {busy === 'adopt' ? '\u2026' : 'Use this'}
              </button>
            </div>
          </div>
        </Row>
      )}

      {problem && (
        <Row
          label="That upload was refused"
          state="warn"
          // The reason, in the backend's words. It names the type it saw and
          // the size limit, which is what tells someone what to do next.
          detail={problem}
        />
      )}
    </>
  );
}
