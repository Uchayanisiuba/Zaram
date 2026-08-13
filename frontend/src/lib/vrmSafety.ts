/**
 * An avatar file is something somebody else wrote.
 *
 * `core/untrusted.py` states the rule for documents: only what the user typed
 * may instruct, written as an allow-list of one value so a channel added later
 * is refused by omission rather than permitted by it. A `.vrm` is the same
 * class of thing arriving through a different door, and it is worse in one
 * specific way.
 *
 * **glTF can reference external URIs, and the browser fetches them.** `buffers`
 * and `images` each carry an optional `uri`, and an absolute `https://` one is
 * resolved by the loader with an ordinary request. That request leaves the
 * machine, and no gate in this product can see it — `EgressGate` intercepts what
 * the *backend* sends, and `check-no-remote-assets.mjs` scans *source*. A URL
 * sitting inside a binary asset is invisible to both. Rule 3 says every byte
 * that leaves is logged; a hostile avatar breaks that with a data file and
 * nothing anywhere reports it.
 *
 * It is also a working beacon: load the avatar, and whoever authored it learns
 * your IP and when you opened the app.
 *
 * **So the policy is an allow-list of one form: embedded, or `data:`.** Not a
 * blocklist of suspicious hosts, and not "same origin is fine" — a relative URI
 * still means the loader goes looking for a file beside one the user dropped in,
 * which is a filesystem read nobody asked for. The bundled avatar is a GLB with
 * everything embedded, so the rule costs the shipping product nothing and the
 * refusal only ever fires on a file that was going to reach out.
 *
 * **This refuses; it does not sanitise.** Same reasoning as `scan()` on the
 * ingest side: rewriting somebody's asset to strip a URI produces a file that is
 * subtly not what they made, and teaches the user nothing. A named refusal is
 * better than a silent repair.
 */

/** Chunk and container constants from the glTF 2.0 binary spec. */
const GLB_MAGIC = 0x46546c67 // 'glTF', little-endian
const CHUNK_JSON = 0x4e4f534a // 'JSON'
const GLB_HEADER_BYTES = 12
const CHUNK_HEADER_BYTES = 8

export interface VrmVerdict {
  ok: boolean
  /** Plain language, shown to the user. Empty when ok. */
  reason: string
  /** The offending URIs, for a detail view. Never rendered as the headline. */
  external: string[]
}

const ALLOWED = 'ok'

/**
 * Read the JSON chunk out of a GLB, or parse a plain `.gltf`.
 *
 * Returns `null` when the bytes are neither, which the caller treats as a
 * refusal rather than as permission — a file this cannot read is a file whose
 * URIs cannot be checked, and "could not inspect" must never mean "allowed".
 */
export function readGltfJson(buffer: ArrayBuffer): Record<string, unknown> | null {
  if (buffer.byteLength < GLB_HEADER_BYTES) return null

  const view = new DataView(buffer)
  if (view.getUint32(0, true) !== GLB_MAGIC) {
    // Not binary. A `.gltf` is UTF-8 JSON; try that before giving up.
    try {
      const text = new TextDecoder().decode(buffer)
      const parsed: unknown = JSON.parse(text)
      return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null
    } catch {
      return null
    }
  }

  // Walk chunks until the JSON one. It is required to be first by the spec,
  // but reading it positionally would trust a file to be well-formed, and this
  // whole module exists because it might not be.
  let offset = GLB_HEADER_BYTES
  while (offset + CHUNK_HEADER_BYTES <= buffer.byteLength) {
    const length = view.getUint32(offset, true)
    const type = view.getUint32(offset + 4, true)
    const start = offset + CHUNK_HEADER_BYTES
    if (start + length > buffer.byteLength) return null

    if (type === CHUNK_JSON) {
      try {
        const text = new TextDecoder().decode(new Uint8Array(buffer, start, length))
        const parsed: unknown = JSON.parse(text)
        return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null
      } catch {
        return null
      }
    }
    // Chunks are 4-byte aligned.
    offset = start + length + ((4 - (length % 4)) % 4)
  }
  return null
}

/** Whether a `uri` value is one the loader may resolve without leaving. */
export function isEmbeddedUri(uri: unknown): boolean {
  if (typeof uri !== 'string') return false
  const trimmed = uri.trim()
  if (!trimmed) return false
  // Case-insensitive: `DATA:` and `Data:` are the same scheme to a browser, and
  // a check that only knew the lower-case spelling would be trivially evaded.
  return trimmed.slice(0, 5).toLowerCase() === 'data:'
}

/**
 * Every `uri` in the document that is not embedded.
 *
 * Walks the whole object rather than reading `buffers` and `images` by name.
 * Those are the two the spec defines today, and an extension is free to add a
 * third — `VRMC_materials_mtoon` alone carries several texture references, and
 * a check that hardcoded two keys would pass a file whose beacon sat in an
 * extension block. The same reasoning that made `applyTextureFiltering` walk
 * materials instead of naming `map` and `normalMap`.
 */
export function findExternalUris(node: unknown, seen = new Set<unknown>()): string[] {
  if (node === null || typeof node !== 'object') return []
  if (seen.has(node)) return []
  seen.add(node)

  const found: string[] = []

  if (Array.isArray(node)) {
    for (const item of node) found.push(...findExternalUris(item, seen))
    return found
  }

  for (const [key, value] of Object.entries(node as Record<string, unknown>)) {
    if (key === 'uri' && typeof value === 'string') {
      if (!isEmbeddedUri(value)) found.push(value)
      continue
    }
    found.push(...findExternalUris(value, seen))
  }
  return found
}

/**
 * May this avatar be loaded?
 *
 * The reason text is written for the person who dropped the file in, not for a
 * log: it says what was found and what it would have done, because "this avatar
 * was refused" with no explanation is indistinguishable from a broken loader.
 */
export function inspectAvatar(buffer: ArrayBuffer): VrmVerdict {
  const json = readGltfJson(buffer)
  if (json === null) {
    return {
      ok: false,
      reason:
        'This file could not be read as a VRM, so what it would load could not be checked.',
      external: [],
    }
  }

  const external = findExternalUris(json)
  if (external.length > 0) {
    const one = external.length === 1
    return {
      ok: false,
      reason:
        `This avatar asks to download ${one ? 'a file' : `${external.length} files`} ` +
        `from the internet while it loads, which would tell whoever made it that you ` +
        `opened Zaram. Avatars have to be self-contained.`,
      external,
    }
  }

  return { ok: true, reason: ALLOWED, external: [] }
}
