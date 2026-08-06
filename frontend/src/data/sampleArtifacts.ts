/**
 * ⚠️ SAMPLE DATA — NOT REAL. Nothing here comes from the backend.
 *
 * Every artifact below is invented, and no file exists on disk for any of them.
 * This module exists so the Work surface can be designed before the generative
 * pipeline exists to fill it; it is deleted the moment Work reads real
 * artifacts, and it must never ship behind a code path a user can reach without
 * knowing it is a sample.
 *
 * The rule this is deliberately bending: CLAUDE.md says never render invented
 * values, because a status indicator over hardcoded data is worse than no
 * indicator. That rule is about *the system reporting on itself* — an orb
 * claiming "local only" or a count claiming 1,247 facts. This is a design
 * exercise for a surface with no data source yet, which is a different thing,
 * and it is only safe while three conditions hold:
 *
 *   1. It is unmistakably labelled here and at every import site.
 *   2. The surface says so on screen. It does — see the sample banner.
 *   3. Actions that cannot work are inert and say why, rather than being wired
 *      to something plausible. Download does nothing and states that there is
 *      no file, because a download button that produces a fabricated invoice is
 *      exactly the failure the rule is guarding against.
 *
 * The shape here is a first draft of the artifact model that Session 3 has to
 * formalise, since Work and the in-conversation file cards both consume it.
 * Treat divergence between this and the real model as a bug in this file.
 */

export type ArtifactKind = 'invoice' | 'document' | 'spreadsheet' | 'chart';

/** Where a fact or artifact came from. Mirrors `ChatSource` in chatClient so
 *  the two do not drift — provenance is one idea, not two. */
export interface ArtifactSource {
  kind: string;
  url: string | null;
  title: string | null;
}

export interface Artifact {
  id: string;
  filename: string;
  kind: ArtifactKind;
  projectId: string;
  /** Epoch seconds. */
  createdAt: number;
  sizeBytes: number;
  /** The conversation that produced it. Work exists to hold output *with* the
   *  conversation that made it — without this it is a file browser, which the
   *  operating system already provides. */
  conversation: { id: string; title: string };
  /** What the artifact drew on. Claims inside a generated document trace back
   *  to these, the same as citations in a reply. */
  sources: ArtifactSource[];
  /** Stand-in for a rendered preview. Real previews are PDF in v1 and a
   *  lightweight HTML render for .docx/.xlsx later. */
  previewText: string;
}

export interface Project {
  id: string;
  name: string;
}

/** SAMPLE. Two projects, because filtering by one project is meaningless with
 *  only one to filter to. */
export const SAMPLE_PROJECTS: Project[] = [
  { id: 'meridian', name: 'Meridian Rebrand' },
  { id: 'harbour', name: 'Harbour Lane Studio' },
];

const DAY = 86_400;
const now = () => Math.floor(Date.now() / 1000);

/** Dates are relative to load so the list always reads plausibly rather than
 *  drifting into "2 years ago" as this file ages on disk. */
const daysAgo = (n: number) => now() - n * DAY;

/** SAMPLE ARTIFACTS — 20 across two projects, four kinds, spread over a
 *  quarter so the ordering and the date column have something to show. */
export const SAMPLE_ARTIFACTS: Artifact[] = [
  {
    id: 'a01',
    filename: 'invoice-2026-041.pdf',
    kind: 'invoice',
    projectId: 'meridian',
    createdAt: daysAgo(1),
    sizeBytes: 48_210,
    conversation: { id: 'c01', title: 'Invoice for the March retainer' },
    sources: [
      { kind: 'memory', url: 'memory:rate-meridian', title: 'Meridian day rate is £480' },
      { kind: 'memory', url: 'memory:terms-meridian', title: 'Meridian pays on 30-day terms' },
    ],
    previewText:
      'INVOICE 2026-041\n\nMeridian Ltd\n14 Calder Street\n\nRetainer — March 2026\n8 days @ £480/day        £3,840.00\n\nTerms: 30 days net\nDue: 5 September 2026',
  },
  {
    id: 'a02',
    filename: 'brand-guidelines-v3.docx',
    kind: 'document',
    projectId: 'meridian',
    createdAt: daysAgo(3),
    sizeBytes: 1_204_880,
    conversation: { id: 'c02', title: 'Tightening the tone-of-voice section' },
    sources: [
      { kind: 'memory', url: 'memory:brief-meridian', title: 'Client brief — Meridian rebrand' },
      { kind: 'memory', url: 'memory:review-apr', title: 'April review: less corporate' },
    ],
    previewText:
      'MERIDIAN BRAND GUIDELINES\nVersion 3\n\n1. Voice\nDirect, never brisk. We explain before we ask.\n\n2. Colour\nPrimary — Calder Blue #1F3A5F',
  },
  {
    id: 'a03',
    filename: 'q1-spend.xlsx',
    kind: 'spreadsheet',
    projectId: 'meridian',
    createdAt: daysAgo(4),
    sizeBytes: 22_140,
    conversation: { id: 'c03', title: 'Where did the Q1 budget go' },
    sources: [{ kind: 'memory', url: 'memory:receipts-q1', title: 'Q1 receipts, 41 items' }],
    previewText:
      'Category        Q1        vs Q4\nPrint           £2,100    +12%\nPhotography     £3,600    −4%\nLicensing       £890      +2%\nTotal           £6,590    +5%',
  },
  {
    id: 'a04',
    filename: 'spend-by-category.png',
    kind: 'chart',
    projectId: 'meridian',
    createdAt: daysAgo(4),
    sizeBytes: 96_400,
    conversation: { id: 'c03', title: 'Where did the Q1 budget go' },
    sources: [{ kind: 'memory', url: 'memory:receipts-q1', title: 'Q1 receipts, 41 items' }],
    previewText: '[bar chart — spend by category, Q1 2026]',
  },
  {
    id: 'a05',
    filename: 'proposal-phase-two.pdf',
    kind: 'document',
    projectId: 'meridian',
    createdAt: daysAgo(9),
    sizeBytes: 318_900,
    conversation: { id: 'c04', title: 'What phase two should cover' },
    sources: [
      { kind: 'memory', url: 'memory:brief-meridian', title: 'Client brief — Meridian rebrand' },
      { kind: 'memory', url: 'memory:scope-note', title: 'Phase one excluded motion' },
    ],
    previewText:
      'PHASE TWO — PROPOSAL\n\nScope\nMotion identity, social templates, and a\nsix-week handover.\n\nEstimate: 14 days',
  },
  {
    id: 'a06',
    filename: 'invoice-2026-038.pdf',
    kind: 'invoice',
    projectId: 'meridian',
    createdAt: daysAgo(16),
    sizeBytes: 47_880,
    conversation: { id: 'c05', title: 'February invoice' },
    sources: [{ kind: 'memory', url: 'memory:rate-meridian', title: 'Meridian day rate is £480' }],
    previewText:
      'INVOICE 2026-038\n\nRetainer — February 2026\n7 days @ £480/day        £3,360.00\n\nPAID 2 August 2026',
  },
  {
    id: 'a07',
    filename: 'moodboard-notes.docx',
    kind: 'document',
    projectId: 'meridian',
    createdAt: daysAgo(21),
    sizeBytes: 88_300,
    conversation: { id: 'c06', title: 'Notes from the moodboard call' },
    sources: [{ kind: 'memory', url: 'memory:call-0714', title: 'Call, 14 July' }],
    previewText: 'MOODBOARD — NOTES\n\nLiked: the Calder blue, the tighter grid.\nCut: the serif headline.',
  },
  {
    id: 'a08',
    filename: 'timeline-phase-two.png',
    kind: 'chart',
    projectId: 'meridian',
    createdAt: daysAgo(23),
    sizeBytes: 74_050,
    conversation: { id: 'c04', title: 'What phase two should cover' },
    sources: [{ kind: 'memory', url: 'memory:scope-note', title: 'Phase one excluded motion' }],
    previewText: '[gantt — phase two, six weeks]',
  },
  {
    id: 'a09',
    filename: 'rate-card-2026.xlsx',
    kind: 'spreadsheet',
    projectId: 'meridian',
    createdAt: daysAgo(31),
    sizeBytes: 18_720,
    conversation: { id: 'c07', title: 'Updating the rate card' },
    sources: [{ kind: 'memory', url: 'memory:rate-meridian', title: 'Meridian day rate is £480' }],
    previewText: 'Service          Day rate\nIdentity         £480\nMotion           £520\nConsulting       £600',
  },
  {
    id: 'a10',
    filename: 'invoice-2026-035.pdf',
    kind: 'invoice',
    projectId: 'meridian',
    createdAt: daysAgo(46),
    sizeBytes: 47_100,
    conversation: { id: 'c08', title: 'January invoice' },
    sources: [{ kind: 'memory', url: 'memory:terms-meridian', title: 'Meridian pays on 30-day terms' }],
    previewText: 'INVOICE 2026-035\n\nRetainer — January 2026\n9 days @ £480/day        £4,320.00\n\nPAID',
  },

  {
    id: 'a11',
    filename: 'quote-harbour-fitout.pdf',
    kind: 'invoice',
    projectId: 'harbour',
    createdAt: daysAgo(2),
    sizeBytes: 61_400,
    conversation: { id: 'c09', title: 'Quoting the studio fit-out' },
    sources: [
      { kind: 'memory', url: 'memory:harbour-brief', title: 'Harbour Lane wants it done by October' },
      { kind: 'memory', url: 'memory:materials-q', title: 'Oak ply lead time is 3 weeks' },
    ],
    previewText:
      'QUOTE — HARBOUR LANE STUDIO\n\nFit-out, 42 sqm\nMaterials                £4,180\nLabour, 11 days          £3,300\n\nValid 30 days — expires 5 September 2026',
  },
  {
    id: 'a12',
    filename: 'site-survey.docx',
    kind: 'document',
    projectId: 'harbour',
    createdAt: daysAgo(5),
    sizeBytes: 402_600,
    conversation: { id: 'c10', title: 'Writing up the survey' },
    sources: [{ kind: 'memory', url: 'memory:survey-0729', title: 'Survey visit, 29 July' }],
    previewText:
      'SITE SURVEY — HARBOUR LANE\n\nFloor: level to within 4mm.\nDamp: none found.\nPower: single ring, needs a second.',
  },
  {
    id: 'a13',
    filename: 'materials-costing.xlsx',
    kind: 'spreadsheet',
    projectId: 'harbour',
    createdAt: daysAgo(6),
    sizeBytes: 31_050,
    conversation: { id: 'c11', title: 'Costing the materials' },
    sources: [{ kind: 'memory', url: 'memory:materials-q', title: 'Oak ply lead time is 3 weeks' }],
    previewText: 'Item          Qty    Unit     Total\nOak ply       14     £86      £1,204\nBirch ply     6      £52      £312',
  },
  {
    id: 'a14',
    filename: 'cost-breakdown.png',
    kind: 'chart',
    projectId: 'harbour',
    createdAt: daysAgo(6),
    sizeBytes: 82_900,
    conversation: { id: 'c11', title: 'Costing the materials' },
    sources: [{ kind: 'memory', url: 'memory:materials-q', title: 'Oak ply lead time is 3 weeks' }],
    previewText: '[pie — materials vs labour vs contingency]',
  },
  {
    id: 'a15',
    filename: 'schedule-october.png',
    kind: 'chart',
    projectId: 'harbour',
    createdAt: daysAgo(12),
    sizeBytes: 68_300,
    conversation: { id: 'c12', title: 'Can we hit October' },
    sources: [
      { kind: 'memory', url: 'memory:harbour-brief', title: 'Harbour Lane wants it done by October' },
    ],
    previewText: '[gantt — fit-out schedule to 14 October]',
  },
  {
    id: 'a16',
    filename: 'contract-harbour.pdf',
    kind: 'document',
    projectId: 'harbour',
    createdAt: daysAgo(18),
    sizeBytes: 244_700,
    conversation: { id: 'c13', title: 'Drafting the contract' },
    sources: [
      { kind: 'memory', url: 'memory:harbour-brief', title: 'Harbour Lane wants it done by October' },
      { kind: 'memory', url: 'memory:std-terms', title: 'Standard terms: 50% on signature' },
    ],
    previewText:
      'AGREEMENT\n\n3. Payment\n50% on signature, balance on completion.\nLate payment attracts 4% above base.',
  },
  {
    id: 'a17',
    filename: 'invoice-harbour-001.pdf',
    kind: 'invoice',
    projectId: 'harbour',
    createdAt: daysAgo(19),
    sizeBytes: 44_600,
    conversation: { id: 'c14', title: 'Deposit invoice' },
    sources: [{ kind: 'memory', url: 'memory:std-terms', title: 'Standard terms: 50% on signature' }],
    previewText: 'INVOICE HL-001\n\nDeposit, 50% on signature   £3,740.00\n\nTerms: 14 days',
  },
  {
    id: 'a18',
    filename: 'lighting-spec.docx',
    kind: 'document',
    projectId: 'harbour',
    createdAt: daysAgo(27),
    sizeBytes: 156_200,
    conversation: { id: 'c15', title: 'What lighting the space needs' },
    sources: [{ kind: 'memory', url: 'memory:survey-0729', title: 'Survey visit, 29 July' }],
    previewText: 'LIGHTING SPEC\n\nTrack: 3 runs, 2.4m.\nColour temperature: 3000K throughout.',
  },
  {
    id: 'a19',
    filename: 'hours-log.xlsx',
    kind: 'spreadsheet',
    projectId: 'harbour',
    createdAt: daysAgo(38),
    sizeBytes: 26_900,
    conversation: { id: 'c16', title: 'How many hours so far' },
    sources: [],
    previewText: 'Week       Hours\n29 Jul     18.5\n5 Aug      22.0\n12 Aug     16.5',
  },
  {
    id: 'a20',
    filename: 'client-update-aug.docx',
    kind: 'document',
    projectId: 'harbour',
    createdAt: daysAgo(58),
    sizeBytes: 74_800,
    conversation: { id: 'c17', title: 'Summarise the week as a client update' },
    sources: [
      { kind: 'memory', url: 'memory:survey-0729', title: 'Survey visit, 29 July' },
      { kind: 'memory', url: 'memory:materials-q', title: 'Oak ply lead time is 3 weeks' },
    ],
    previewText:
      'UPDATE — WEEK OF 5 AUGUST\n\nSurvey complete, no damp.\nPly ordered, arriving w/c 26 August.',
  },
];

export const KIND_LABELS: Record<ArtifactKind, string> = {
  invoice: 'Invoices',
  document: 'Documents',
  spreadsheet: 'Spreadsheets',
  chart: 'Charts',
};
