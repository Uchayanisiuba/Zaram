/**
 * The page a reply stands for -- written out in full, or as changes to an earlier one.
 *
 * 11 October 2026. A reply can now carry a page three ways: the whole page (as
 * before), SEARCH/REPLACE changes to the page the conversation already has, or
 * changes to one of Zaram's tested starting points, named on a line of its own
 * (`Starting from: voxel-world`). Every place that runs, saves, checks or asks
 * about a page goes through here, so all of them see the same page -- the
 * preview cannot run one thing while the check tested another.
 *
 * Pure: the starting points are passed in, already fetched (`starterStore`), and
 * so are the person's attached pictures (`pictureStore`), which ride on the page
 * by name and are put in only when it is run, checked or saved
 * (`lib/pagePictures.ts`).
 */
import type { AppFile } from '@/lib/appFiles';
import { applyEdits, asFiles, extractEdits, pageOf, repairLoops } from '@/lib/pageEdits';
import type { PictureMap } from '@/lib/pagePictures';
import { extractPreviewable, type PreviewableBlock } from '@/lib/previewableCode';

/** The line that names a starting point: `Starting from: voxel-world`. */
const STARTING_FROM = /^[ \t>*_`]*starting from:?[*_ \t`]*([a-z0-9][a-z0-9-]*)/im;

export function starterNamed(text: string): string | null {
  return STARTING_FROM.exec(text || '')?.[1]?.toLowerCase() ?? null;
}

export interface ReplyPage extends PreviewableBlock {
  /** Set when the page was made from changes rather than written out whole. */
  edited?: {
    /** The starting point the changes were made to, if one was named. */
    starter?: string;
    applied: number;
    /** One plain sentence for each change that matched nothing. */
    failed: string[];
  };
  /** Loops Zaram put a missing `++` back into, said to the person. */
  repaired?: string[];
}

interface Turn {
  role: string;
  text: string;
}

function filesOf(block: PreviewableBlock): AppFile[] {
  return block.files ? block.files.map((f) => ({ ...f })) : asFiles(block.code);
}

function finish(files: AppFile[], extra: Partial<ReplyPage>, pictures: PictureMap): ReplyPage | null {
  const repaired: string[] = [];
  const mended = files.map((f) => {
    if (!/\.(?:m?js|html?)$/i.test(f.path)) return f;
    const result = repairLoops(f.code);
    repaired.push(...result.repaired.map((r) => (files.length > 1 ? `${f.path}: ${r}` : r)));
    return { ...f, code: result.code };
  });
  const page = pageOf(mended);
  if (!page) return null;
  return {
    language: 'html',
    label: mended.length > 1 ? 'App' : 'HTML',
    code: page.code,
    ...(mended.length > 1 ? { files: mended, modules: page.modules } : {}),
    ...extra,
    ...(repaired.length ? { repaired } : {}),
    // The pictures stand beside the page and are put in only when it is run,
    // checked or saved (`inlinePictures`): this page keeps the names the model
    // wrote, which is what it must be shown on a follow-up.
    ...(Object.keys(pictures).length ? { pictures } : {}),
  };
}

/**
 * The page for `turns[index]`, or `null` when that reply carries none.
 *
 * Changes are applied to the page of the nearest earlier reply that has one --
 * itself resolved the same way -- unless the reply names a starting point, which
 * then is the base. A reply that names neither and has nothing to change has no
 * page. `starters` maps a starting point's name to its page.
 */
export function pageForTurn(
  turns: readonly Turn[],
  index: number,
  starters: Readonly<Record<string, string>> = {},
  pictures: PictureMap = {},
): ReplyPage | null {
  const turn = turns[index];
  if (!turn || turn.role !== 'assistant') return null;
  const text = turn.text;
  const edits = extractEdits(text);
  const starter = starterNamed(text);
  const own = extractPreviewable(text);

  if (!edits.length && !starter) {
    if (!own) return null;
    if (own.language !== 'html') return own;
    return finish(filesOf(own), {}, pictures);
  }

  let base: AppFile[] | null = null;
  if (starter && starters[starter]) base = asFiles(starters[starter]);
  else if (!starter) {
    for (let i = index - 1; i >= 0 && !base; i--) {
      if (turns[i].role !== 'assistant') continue;
      const earlier = pageForTurn(turns, i, starters, pictures);
      if (earlier && earlier.language === 'html') base = filesOf(earlier);
    }
  }
  if (!base) return own && own.language === 'html' ? finish(filesOf(own), {}, pictures) : null;

  // Files written out whole in the same reply replace the base's copy first.
  if (own && own.language === 'html' && own.files) {
    for (const file of own.files) {
      const at = base.findIndex((f) => f.path.toLowerCase() === file.path.toLowerCase());
      if (at >= 0) base[at] = file;
      else base.push(file);
    }
  }
  const result = applyEdits(base, edits);
  return finish(
    result.files,
    {
      edited: {
        ...(starter ? { starter } : {}),
        applied: result.applied,
        failed: result.failed.map(({ reason }, i) => `Change ${i + 1}: ${reason}.`),
      },
    },
    pictures,
  );
}

/** Every starting point a set of turns names, so they can be fetched first. */
export function startersNamedIn(turns: readonly Turn[]): string[] {
  const names = new Set<string>();
  for (const t of turns) {
    if (t.role !== 'assistant') continue;
    const name = starterNamed(t.text);
    if (name) names.add(name);
  }
  return [...names];
}
