/**
 * First run — what is missing, what it costs, and what works anyway.
 *
 * This stands where the composer stands, and only when the backend has said
 * plainly that chat cannot work. That placement is the whole design: the
 * failure is explained at the exact spot where it would otherwise be silent.
 * A new user who types into a dead box and watches nothing happen concludes the
 * product does not work; a new user who is told what is missing, what it would
 * cost, and what they can do meanwhile is a user who explores.
 *
 * Four rules run through it, each easy to undo by accident:
 *
 * **The price is on the button.** `downloadLabel` is rendered beside the label
 * itself, never in a tooltip and never behind a disclosure. Naming a fix
 * without naming its cost is not a choice someone on a metered connection can
 * make — the same reason the OCR extra quotes 321 MB rather than saying
 * "install Docling".
 *
 * **No size at all when there is no download.** Not "0 MB", which reads as free
 * rather than as absent. `readinessClient` collapses both spellings to null so
 * this file only has to check one thing.
 *
 * **Nothing here acts on its own.** `/readiness` reports and never fetches. Of
 * the offers it returns, exactly one can be carried out by this screen today —
 * looking around — and the rest say so rather than being buttons that swallow a
 * click. That is the pack catalogue's rule applied to setup: unavailable things
 * are shown, greyed, and honestly graded. A button that appears to work and
 * does nothing is the single worst thing to put on a first-run screen.
 *
 * **No model filenames.** Every string describing an offer comes from the
 * payload, which is asserted clean on the backend side. The payload also
 * carries the model's *name*, for whatever eventually pulls it, and this screen
 * deliberately never reads it — the target user is not technical and a filename
 * is not a thing they chose.
 *
 * One sentence is composed here rather than taken: the line naming the date on
 * the model list. Its only variable is that date, it says nothing about the
 * model, and it exists because a recommendation is only as current as the list
 * behind it.
 */
import { useState } from 'react';

import CloudKeyForm from './CloudKeyForm';
import ModelPull from './ModelPull';
import type { ReadinessOffer, ReadinessReport } from '@/services/readinessClient';

interface FirstRunPanelProps {
  report: ReadinessReport;
  /** Chosen "look around first". */
  onExplore: () => void;
  /**
   * A provider was configured, so readiness should be asked again.
   *
   * **Required, not optional**, for the reason `ChatSurface`'s own `navigate`
   * prop is required: a missing handler here would leave the setup screen
   * standing over a product that had just become able to answer, and the
   * failure would be silent. A compile error at the call site is the cheaper
   * version of that bug.
   */
  onConnected: () => void;
}

/**
 * Whether choosing this does anything today.
 *
 * Exploring is a navigation and needs nothing behind it. **Storing a cloud key
 * was admitted on 29 August 2026** — `CloudKeyForm` is its executor, and it
 * qualified before the other two because its backend already existed:
 * `POST /providers/cloud` writes the configuration and is effective without a
 * restart, so the offer can be carried out here and now rather than promising
 * something about the next launch.
 *
 * **Pulling a model was admitted on 5 September 2026** — `ModelPull` is its
 * executor, over `POST /providers/pull`, and it qualified on the same terms:
 * the download happens here, streams its progress here, and the screen
 * disappears by itself when the model can answer. The route decides *which*
 * model from the same manifest lookup that produced this offer, so the thing
 * fetched is the thing priced on the button.
 *
 * Installing an engine still has no executor. Inventing an instruction for it
 * here — a command to type, a site to visit — would put a value in the
 * interface that nothing else in the product maintains. When that executor
 * lands, this function is where it is admitted.
 */
function canBeCarriedOut(kind: string): boolean {
  return kind === 'explore' || kind === 'use_cloud_key' || kind === 'pull_model';
}

export default function FirstRunPanel({ report, onExplore, onConnected }: FirstRunPanelProps) {
  const [openOffer, setOpenOffer] = useState<string | null>(null);
  return (
    <section
      aria-label="Setting Zaram up"
      className="flex-1 overflow-y-auto"
      data-testid="first-run"
    >
      <div className="flex flex-col gap-6 p-6">
        <div>
          <p
            className="text-[10px] uppercase tracking-wider mb-2"
            style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-display)' }}
          >
            Before you start
          </p>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--color-text)' }}>
            {report.summary}
          </p>
        </div>

        {report.offers.length > 0 && (
          <ul className="flex flex-col gap-2 list-none p-0 m-0">
            {report.offers.map((offer) => (
              <li key={offer.kind} className="flex flex-col gap-2">
                <OfferRow
                  offer={offer}
                  onChoose={() => {
                    if (offer.kind === 'use_cloud_key' || offer.kind === 'pull_model') {
                      // Toggled rather than navigated. The executor belongs
                      // under the offer it belongs to, where the price and the
                      // detail above it stay readable — a setup screen that
                      // replaces itself loses the context that made the choice
                      // make sense.
                      setOpenOffer((current) => (current === offer.kind ? null : offer.kind));
                      return;
                    }
                    onExplore();
                  }}
                />
                {openOffer === offer.kind && offer.kind === 'use_cloud_key' && (
                  <div className="pl-3">
                    <CloudKeyForm onConnected={onConnected} />
                  </div>
                )}
                {openOffer === offer.kind && offer.kind === 'pull_model' && (
                  <div className="pl-3">
                    {/* Opening the row does not start the download. The size
                        is on the button above and the confirmation is the
                        second press — a gigabyte-scale fetch beginning on a
                        curious click is the one thing a metered connection
                        cannot forgive. */}
                    <ModelPull onFinished={onConnected} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}

        {report.stillWorks.length > 0 && (
          <div>
            {/* Named, not implied. A screen that lists only what is missing
                reads as broken; the same screen listing what already works
                reads as unconfigured, and that is the difference between
                someone exploring and someone uninstalling. */}
            <p
              className="text-[10px] uppercase tracking-wider mb-2"
              style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-display)' }}
            >
              Works right now
            </p>
            <ul className="flex flex-col gap-1.5 list-none p-0 m-0">
              {report.stillWorks.map((line) => (
                <li
                  key={line}
                  className="text-xs leading-relaxed"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  {line}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}

function OfferRow({ offer, onChoose }: { offer: ReadinessOffer; onChoose: () => void }) {
  const available = canBeCarriedOut(offer.kind);

  return (
    <button
      type="button"
      onClick={available ? onChoose : undefined}
      // Disabled rather than absent, and readable rather than dimmed to
      // nothing: the option is real, it is what the user will eventually
      // choose, and hiding it would make the screen claim there are fewer ways
      // out than there are.
      aria-disabled={available ? undefined : true}
      disabled={!available}
      data-offer={offer.kind}
      className="w-full text-left rounded-xl border p-3 transition-colors"
      style={{
        borderColor: available ? 'var(--color-cyan-light)' : 'rgba(255,255,255,0.08)',
        background: available ? 'rgba(125,211,252,0.08)' : 'transparent',
        cursor: available ? 'pointer' : 'default',
      }}
    >
      <span className="flex items-baseline gap-2 flex-wrap">
        <span
          className="text-sm"
          style={{ color: available ? 'var(--color-text)' : 'var(--color-text-muted)' }}
        >
          {offer.label}
        </span>
        {/* On the button, never in a tooltip. Rendered only when there is a
            figure — an absent download shows nothing at all. */}
        {offer.downloadLabel && (
          <span
            className="text-[11px]"
            style={{
              color: 'var(--color-text-muted)',
              fontFamily: 'var(--font-mono, ui-monospace, monospace)',
            }}
          >
            {offer.downloadLabel} download
          </span>
        )}
      </span>
      <span
        className="block mt-1 text-xs leading-relaxed"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {offer.detail}
      </span>
      {/* The date on the list the model was chosen from. Shown because a
          recommendation is only as current as the list behind it, and a screen
          that names a model without saying when the advice was written claims
          more currency than the manifest has. Absent when the recommendation
          came from the fallback — nothing dates a fallback. */}
      {offer.recommendedOn && (
        <span
          className="block mt-1 text-[11px] leading-relaxed"
          style={{ color: 'var(--color-text-muted)', opacity: 0.75 }}
        >
          From Zaram’s model list, dated {offer.recommendedOn}.
        </span>
      )}
      {/* Under the detail, not beside the label, and as a sentence rather than
          a shouted pill. The detail describes what the option *is*; this says
          why the button will not do it. Without the second line the first reads
          as a promise the button breaks — "installs the engine" on something
          that installs nothing.
          It says only what is true today and nothing about what will change,
          because a key set after launch is not picked up by a running process
          and "Zaram will notice" would be right about one offer and wrong about
          the other. */}
      {!available && (
        <span
          className="block mt-1.5 text-xs leading-relaxed"
          style={{ color: 'var(--color-text-muted)', opacity: 0.85 }}
        >
          Zaram can’t set this up for you yet.
        </span>
      )}
    </button>
  );
}
