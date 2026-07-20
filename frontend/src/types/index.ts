export type { Artifact, ArtifactType, ArtifactCreateInput, ArtifactUpdateInput, ArtifactFilter, ArtifactVersion, ArtifactStats } from './artifacts';

export type { PanelId, PanelConfig, WorkspaceLayout } from './workspace';

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  model?: string
  status?: 'sending' | 'streaming' | 'complete' | 'error'
}

export interface Model {
  id: string
  name: string
  provider: string
  size?: string
  description?: string
  status?: 'active' | 'inactive'
  ram?: string
  contextLength?: number
  capabilities?: string[]
}

export interface Provider {
  id: string
  name: string
  type: string
  endpoint?: string
  models: Model[]
}

export interface Voice {
  id: string
  name: string
  gender?: string
  language?: string
  theme?: string
  accent?: string
  description?: string
}

export type CharacterTheme = 'alexis' | 'aria' | 'nova' | 'luna' | 'kai' | 'leo'
