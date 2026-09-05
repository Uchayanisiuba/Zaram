/**
 * A hostile avatar cannot phone home.
 *
 * The gap this closes: `check-no-remote-assets.mjs` scans *source* and
 * `EgressGate` intercepts what the *backend* sends, so a URL living inside a
 * binary asset is invisible to both. Rule 3 says every byte that leaves is
 * logged; a `.vrm` with `"uri": "https://…"` in its `images` breaks that with a
 * data file, and nothing anywhere reports it.
 *
 * Built as real GLB bytes rather than as a JSON fixture, because the container
 * parsing is half of what could be wrong — a checker that reads the JSON of a
 * file it cannot parse would pass every hostile GLB by failing to look inside.
 */
import { describe, it, expect } from 'vitest'

import { findExternalUris, inspectAvatar, isEmbeddedUri, readGltfJson } from './vrmSafety'

/** A minimal but structurally real GLB carrying the given glTF JSON. */
function glb(json: unknown): ArrayBuffer {
  const text = new TextEncoder().encode(JSON.stringify(json))
  // Chunks are 4-byte aligned; the JSON chunk pads with spaces.
  const padding = (4 - (text.byteLength % 4)) % 4
  const chunkLength = text.byteLength + padding

  const buffer = new ArrayBuffer(12 + 8 + chunkLength)
  const view = new DataView(buffer)
  view.setUint32(0, 0x46546c67, true) // 'glTF'
  view.setUint32(4, 2, true)
  view.setUint32(8, buffer.byteLength, true)
  view.setUint32(12, chunkLength, true)
  view.setUint32(16, 0x4e4f534a, true) // 'JSON'

  new Uint8Array(buffer, 20).set(text)
  for (let i = 0; i < padding; i++) new Uint8Array(buffer)[20 + text.byteLength + i] = 0x20
  return buffer
}

const SELF_CONTAINED = {
  asset: { version: '2.0' },
  buffers: [{ byteLength: 4 }],
  images: [{ uri: 'data:image/png;base64,iVBORw0KGgo=' }],
}

describe('reading the file at all', () => {
  it('finds the JSON inside a GLB', () => {
    expect(readGltfJson(glb(SELF_CONTAINED))).toMatchObject({ asset: { version: '2.0' } })
  })

  it('reads a plain .gltf too', () => {
    const text = new TextEncoder().encode(JSON.stringify(SELF_CONTAINED))
    expect(readGltfJson(text.buffer as ArrayBuffer)).toMatchObject({ asset: { version: '2.0' } })
  })

  it('refuses what it cannot read, rather than allowing it', () => {
    // "Could not inspect" must never mean "allowed" — a file whose URIs cannot
    // be checked is exactly the file not to load.
    const junk = new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]).buffer
    expect(readGltfJson(junk)).toBeNull()
    expect(inspectAvatar(junk).ok).toBe(false)
  })
})

describe('which URIs are allowed', () => {
  it('allows embedded data URIs', () => {
    expect(isEmbeddedUri('data:image/png;base64,AAAA')).toBe(true)
  })

  it('is not fooled by capitalisation', () => {
    // A browser treats `DATA:` as the same scheme. A check that only knew the
    // lower-case spelling would be trivially evaded.
    expect(isEmbeddedUri('DATA:image/png;base64,AAAA')).toBe(true)
    expect(isEmbeddedUri('Data:image/png;base64,AAAA')).toBe(true)
  })

  it('refuses everything else, including a relative path', () => {
    // Not just remote hosts: a relative URI still sends the loader looking for
    // a file beside one the user dropped in, which is a read nobody asked for.
    expect(isEmbeddedUri('https://tracker.example/beacon.png')).toBe(false)
    expect(isEmbeddedUri('//tracker.example/beacon.png')).toBe(false)
    expect(isEmbeddedUri('textures/skin.png')).toBe(false)
    expect(isEmbeddedUri('')).toBe(false)
  })
})

describe('inspecting an avatar', () => {
  it('passes a self-contained one', () => {
    const verdict = inspectAvatar(glb(SELF_CONTAINED))

    expect(verdict.ok).toBe(true)
    expect(verdict.external).toEqual([])
  })

  it('refuses one that would fetch an image while loading', () => {
    const verdict = inspectAvatar(
      glb({ ...SELF_CONTAINED, images: [{ uri: 'https://tracker.example/beacon.png' }] }),
    )

    expect(verdict.ok).toBe(false)
    expect(verdict.external).toEqual(['https://tracker.example/beacon.png'])
    // The reason is written for the person who dropped the file in. A refusal
    // with no explanation is indistinguishable from a broken loader.
    expect(verdict.reason).toContain('download')
  })

  it('refuses one that would fetch its geometry', () => {
    const verdict = inspectAvatar(
      glb({ ...SELF_CONTAINED, buffers: [{ uri: 'https://tracker.example/mesh.bin' }] }),
    )

    expect(verdict.ok).toBe(false)
  })

  it('finds a URI hidden in an extension block', () => {
    // The reason `findExternalUris` walks the whole document rather than
    // reading `buffers` and `images` by name: VRM materials are MToon and carry
    // their own texture references, so a check that knew two keys would pass a
    // file whose beacon sat in an extension. Same reasoning that made
    // `applyTextureFiltering` walk materials instead of naming `map`.
    const verdict = inspectAvatar(
      glb({
        ...SELF_CONTAINED,
        extensions: {
          VRMC_materials_mtoon: { matcapTexture: { uri: 'https://tracker.example/m.png' } },
        },
      }),
    )

    expect(verdict.ok).toBe(false)
    expect(verdict.external).toContain('https://tracker.example/m.png')
  })

  it('counts every offender, not just the first', () => {
    const verdict = inspectAvatar(
      glb({
        ...SELF_CONTAINED,
        images: [{ uri: 'https://a.example/1.png' }, { uri: 'https://b.example/2.png' }],
      }),
    )

    expect(verdict.external).toHaveLength(2)
    expect(verdict.reason).toContain('2 files')
  })

  it('survives a document that references itself', () => {
    // Hand-built glTF from a hostile author need not be a tree. A naive walk
    // would recurse forever and hang the renderer, which is a denial of service
    // dressed as an avatar.
    const cyclic: Record<string, unknown> = { asset: { version: '2.0' } }
    cyclic.self = cyclic

    expect(() => findExternalUris(cyclic)).not.toThrow()
  })
})
