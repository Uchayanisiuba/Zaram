import { create } from 'zustand';
import type { Artifact, ArtifactCreateInput, ArtifactUpdateInput, ArtifactFilter, ArtifactStats, ArtifactVersion } from '@/types/artifacts';

interface ArtifactState {
  artifacts: Map<string, Artifact>;
  openArtifactId: string | null;
  searchQuery: string;
  filter: ArtifactFilter;

  createArtifact: (input: ArtifactCreateInput) => Artifact;
  openArtifact: (id: string) => void;
  closeArtifact: () => void;
  renameArtifact: (id: string, name: string) => void;
  deleteArtifact: (id: string) => void;
  duplicateArtifact: (id: string) => Artifact | null;
  updateArtifact: (id: string, input: ArtifactUpdateInput) => void;
  saveVersion: (id: string) => void;
  revertToVersion: (id: string, versionId: string) => void;
  togglePin: (id: string) => void;
  setSearchQuery: (query: string) => void;
  setFilter: (filter: ArtifactFilter) => void;
  getFilteredArtifacts: () => Artifact[];
  getRecentArtifacts: (limit?: number) => Artifact[];
  getPinnedArtifacts: () => Artifact[];
  getArtifact: (id: string) => Artifact | undefined;
  getStats: () => ArtifactStats;
  clearFilter: () => void;
}

const generateId = () => `${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;

export const useArtifactStore = create<ArtifactState>((set, get) => ({
  artifacts: new Map(),
  openArtifactId: null,
  searchQuery: '',
  filter: {},

  createArtifact: (input: ArtifactCreateInput) => {
    const id = generateId();
    const now = Date.now();
    const initialVersion: ArtifactVersion = {
      id: generateId(),
      artifactId: id,
      content: input.content,
      metadata: input.metadata || {},
      createdAt: now,
      createdBy: 'user',
    };
    const artifact: Artifact = {
      id,
      name: input.name,
      type: input.type,
      content: input.content,
      metadata: input.metadata || {},
      pinned: false,
      versions: [initialVersion],
      currentVersionId: initialVersion.id,
      createdAt: now,
      updatedAt: now,
      createdBy: 'user',
      parentId: input.parentId,
      tags: input.tags || [],
    };
    set((state) => {
      const newArtifacts = new Map(state.artifacts);
      newArtifacts.set(id, artifact);
      return { artifacts: newArtifacts, openArtifactId: id };
    });
    return artifact;
  },

  openArtifact: (id) => set({ openArtifactId: id }),
  closeArtifact: () => set({ openArtifactId: null }),

  renameArtifact: (id, name) => set((state) => {
    const artifact = state.artifacts.get(id);
    if (!artifact) return state;
    const newArtifacts = new Map(state.artifacts);
    newArtifacts.set(id, { ...artifact, name, updatedAt: Date.now() });
    return { artifacts: newArtifacts };
  }),

  deleteArtifact: (id) => set((state) => {
    const newArtifacts = new Map(state.artifacts);
    newArtifacts.delete(id);
    return {
      artifacts: newArtifacts,
      openArtifactId: state.openArtifactId === id ? null : state.openArtifactId,
    };
  }),

  duplicateArtifact: (id) => {
    const artifact = get().artifacts.get(id);
    if (!artifact) return null;
    const newId = generateId();
    const now = Date.now();
    const newVersion: ArtifactVersion = {
      id: generateId(),
      artifactId: newId,
      content: artifact.content,
      metadata: { ...artifact.metadata },
      createdAt: now,
      createdBy: 'user',
    };
    const duplicated: Artifact = {
      ...artifact,
      id: newId,
      name: `${artifact.name} (Copy)`,
      versions: [newVersion],
      currentVersionId: newVersion.id,
      createdAt: now,
      updatedAt: now,
      parentId: id,
      pinned: false,
      tags: [...artifact.tags],
    };
    set((state) => {
      const newArtifacts = new Map(state.artifacts);
      newArtifacts.set(newId, duplicated);
      return { artifacts: newArtifacts };
    });
    return duplicated;
  },

  updateArtifact: (id, input) => set((state) => {
    const artifact = state.artifacts.get(id);
    if (!artifact) return state;
    const updated: Artifact = {
      ...artifact,
      ...(input.name !== undefined && { name: input.name }),
      ...(input.content !== undefined && { content: input.content }),
      ...(input.metadata !== undefined && { metadata: input.metadata }),
      ...(input.pinned !== undefined && { pinned: input.pinned }),
      ...(input.tags !== undefined && { tags: input.tags }),
      updatedAt: Date.now(),
    };
    const newArtifacts = new Map(state.artifacts);
    newArtifacts.set(id, updated);
    return { artifacts: newArtifacts };
  }),

  saveVersion: (id) => set((state) => {
    const artifact = state.artifacts.get(id);
    if (!artifact) return state;
    const newVersion: ArtifactVersion = {
      id: generateId(),
      artifactId: id,
      content: artifact.content,
      metadata: { ...artifact.metadata },
      createdAt: Date.now(),
      createdBy: 'user',
    };
    const updated: Artifact = {
      ...artifact,
      versions: [...artifact.versions, newVersion],
      currentVersionId: newVersion.id,
      updatedAt: Date.now(),
    };
    const newArtifacts = new Map(state.artifacts);
    newArtifacts.set(id, updated);
    return { artifacts: newArtifacts };
  }),

  revertToVersion: (id, versionId) => set((state) => {
    const artifact = state.artifacts.get(id);
    if (!artifact) return state;
    const version = artifact.versions.find((v) => v.id === versionId);
    if (!version) return state;
    const updated: Artifact = {
      ...artifact,
      content: version.content,
      metadata: { ...version.metadata },
      currentVersionId: versionId,
      updatedAt: Date.now(),
    };
    const newArtifacts = new Map(state.artifacts);
    newArtifacts.set(id, updated);
    return { artifacts: newArtifacts };
  }),

  togglePin: (id) => set((state) => {
    const artifact = state.artifacts.get(id);
    if (!artifact) return state;
    const newArtifacts = new Map(state.artifacts);
    newArtifacts.set(id, { ...artifact, pinned: !artifact.pinned });
    return { artifacts: newArtifacts };
  }),

  setSearchQuery: (query) => set({ searchQuery: query }),

  setFilter: (filter) => set({ filter }),

  getFilteredArtifacts: () => {
    const { artifacts, searchQuery, filter } = get();
    let result = Array.from(artifacts.values());

    if (filter.type) {
      result = result.filter((a) => a.type === filter.type);
    }
    if (filter.pinned !== undefined) {
      result = result.filter((a) => a.pinned === filter.pinned);
    }
    if (filter.tag) {
      const tag = filter.tag;
      result = result.filter((a) => a.tags.includes(tag));
    }
    if (filter.parentId) {
      result = result.filter((a) => a.parentId === filter.parentId);
    }
    if (filter.createdBy) {
      result = result.filter((a) => a.createdBy === filter.createdBy);
    }
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (a) =>
          a.name.toLowerCase().includes(q) ||
          a.content.toLowerCase().includes(q) ||
          a.tags.some((t) => t.toLowerCase().includes(q))
      );
    }
    result.sort((a, b) => b.updatedAt - a.updatedAt);
    if (filter.limit) {
      const offset = filter.offset ?? 0;
      result = result.slice(offset, offset + filter.limit);
    }
    return result;
  },

  getRecentArtifacts: (limit = 10) => {
    return get()
      .getFilteredArtifacts()
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .slice(0, limit);
  },

  getPinnedArtifacts: () => {
    return Array.from(get().artifacts.values());
  },

  getArtifact: (id) => get().artifacts.get(id),

  getStats: () => {
    const artifacts = get().artifacts;
    const list = Array.from(artifacts.values());
    const byType: Record<string, number> = {};
    for (const a of list) {
      byType[a.type] = (byType[a.type] || 0) + 1;
    }
    return {
      total: list.length,
      byType: byType as Record<Artifact['type'], number>,
      recentCount: list.filter((a) => Date.now() - a.updatedAt < 7 * 24 * 60 * 60 * 1000).length,
      pinnedCount: list.filter((a) => a.pinned).length,
    };
  },

  clearFilter: () => set({ searchQuery: '', filter: {} }),
}));
