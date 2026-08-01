import { create } from 'zustand';
import { v4 as uuidv4 } from 'uuid';

export type MemoryNodeType = 'code_execution' | 'knowledge_synthesis' | 'user_intent';

export interface MemoryNode {
  id: string;
  type: MemoryNodeType;
  content: string;
  timestamp: Date;
  linkedSurfaceId?: string;
}

interface MemoryStore {
  nodes: MemoryNode[];
  addMemoryNode: (node: Omit<MemoryNode, 'id' | 'timestamp'>) => void;
}

export const useMemoryStore = create<MemoryStore>((set) => ({
  nodes: [],
  addMemoryNode: (node) =>
    set((state) => ({
      nodes: [
        { ...node, id: uuidv4(), timestamp: new Date() },
        ...state.nodes,
      ],
    })),
}));