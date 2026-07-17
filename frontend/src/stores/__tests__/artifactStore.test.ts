import { describe, it, expect } from 'vitest'
import { useArtifactStore } from '../artifactStore'

describe('ArtifactStore', () => {
  it('creates an artifact', () => {
    const store = useArtifactStore.getState()
    store.clearFilter()
    store.closeArtifact()
    const artifact = store.createArtifact({
      name: 'Test Artifact',
      type: 'text',
      content: 'Hello, World!',
    })

    expect(artifact.id).toBeDefined()
    expect(artifact.name).toBe('Test Artifact')
    expect(artifact.type).toBe('text')
    expect(artifact.content).toBe('Hello, World!')
    expect(store.artifacts.size).toBe(1)
  })

  it('opens and closes an artifact', () => {
    const store = useArtifactStore.getState()
    store.clearFilter()
    store.closeArtifact()
    const artifact = store.createArtifact({
      name: 'Openable',
      type: 'text',
      content: 'content',
    })

    store.openArtifact(artifact.id)
    expect(store.openArtifactId).toBe(artifact.id)

    store.closeArtifact()
    expect(store.openArtifactId).toBeNull()
  })

  it('renames an artifact', () => {
    const store = useArtifactStore.getState()
    store.clearFilter()
    store.closeArtifact()
    const artifact = store.createArtifact({
      name: 'Old Name',
      type: 'text',
      content: 'content',
    })

    store.renameArtifact(artifact.id, 'New Name')
    const updated = store.artifacts.get(artifact.id)
    expect(updated?.name).toBe('New Name')
  })

  it('deletes an artifact', () => {
    const store = useArtifactStore.getState()
    store.clearFilter()
    store.closeArtifact()
    const artifact = store.createArtifact({
      name: 'To Delete',
      type: 'text',
      content: 'content',
    })

    expect(store.artifacts.size).toBe(1)
    store.deleteArtifact(artifact.id)
    expect(store.artifacts.size).toBe(0)
  })

  it('duplicates an artifact', () => {
    const store = useArtifactStore.getState()
    store.clearFilter()
    store.closeArtifact()
    const artifact = store.createArtifact({
      name: 'Original',
      type: 'text',
      content: 'content',
    })

    const duplicated = store.duplicateArtifact(artifact.id)
    expect(duplicated).not.toBeNull()
    expect(duplicated?.name).toBe('Original (Copy)')
    expect(duplicated?.parentId).toBe(artifact.id)
    expect(store.artifacts.size).toBe(2)
  })

  it('updates an artifact', () => {
    const store = useArtifactStore.getState()
    store.clearFilter()
    store.closeArtifact()
    const artifact = store.createArtifact({
      name: 'Updatable',
      type: 'text',
      content: 'old',
    })

    store.updateArtifact(artifact.id, { content: 'new', pinned: true })
    const updated = store.artifacts.get(artifact.id)
    expect(updated?.content).toBe('new')
    expect(updated?.pinned).toBe(true)
  })

  it('saves and reverts versions', () => {
    const store = useArtifactStore.getState()
    store.clearFilter()
    store.closeArtifact()
    const artifact = store.createArtifact({
      name: 'Versioned',
      type: 'text',
      content: 'v1',
    })

    store.updateArtifact(artifact.id, { content: 'v2' })
    store.saveVersion(artifact.id)

    const a = store.artifacts.get(artifact.id)!
    expect(a.versions.length).toBe(2)

    store.revertToVersion(artifact.id, a.versions[0].id)
    const reverted = store.artifacts.get(artifact.id)!
    expect(reverted.content).toBe('v1')
  })

  it('toggles pin', () => {
    const store = useArtifactStore.getState()
    store.clearFilter()
    store.closeArtifact()
    const artifact = store.createArtifact({
      name: 'Pin Me',
      type: 'text',
      content: 'content',
    })

    expect(store.artifacts.get(artifact.id)?.pinned).toBe(false)
    store.togglePin(artifact.id)
    expect(store.artifacts.get(artifact.id)?.pinned).toBe(true)
  })

  it('filters and searches artifacts', () => {
    const store = useArtifactStore.getState()
    store.clearFilter()
    store.closeArtifact()
    store.createArtifact({ name: 'Doc', type: 'text', content: 'alpha' })
    store.createArtifact({ name: 'Code', type: 'code', content: 'beta' })
    store.createArtifact({ name: 'Image', type: 'image', content: 'gamma' })

    store.setFilter({ type: 'code' })
    expect(store.getFilteredArtifacts().length).toBe(1)
    expect(store.getFilteredArtifacts()[0].type).toBe('code')

    store.clearFilter()
    store.setSearchQuery('gamma')
    expect(store.getFilteredArtifacts().length).toBe(1)
    expect(store.getFilteredArtifacts()[0].name).toBe('Image')
  })

  it('returns stats', () => {
    const store = useArtifactStore.getState()
    store.clearFilter()
    store.closeArtifact()
    store.createArtifact({ name: 'A', type: 'text', content: '' })
    store.createArtifact({ name: 'B', type: 'code', content: '' })
    store.createArtifact({ name: 'C', type: 'text', content: '', tags: ['tag1'] })

    const stats = store.getStats()
    expect(stats.total).toBe(3)
    expect(stats.byType.text).toBe(2)
    expect(stats.byType.code).toBe(1)
  })
})
