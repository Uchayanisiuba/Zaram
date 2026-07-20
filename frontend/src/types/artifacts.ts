export type ArtifactType = 'text' | 'markdown' | 'code' | 'image' | 'pdf' | 'csv' | 'json' | 'html' | 'audio' | 'video'

export interface ArtifactVersion {
  id: string
  artifactId: string
  content: string
  metadata: Record<string, any>
  createdAt: number
  createdBy: string
}

export interface Artifact {
  id: string
  name: string
  type: ArtifactType
  content: string
  metadata: Record<string, any>
  pinned: boolean
  versions: ArtifactVersion[]
  currentVersionId: string
  createdAt: number
  updatedAt: number
  createdBy: string
  parentId?: string
  tags: string[]
}

export interface ArtifactCreateInput {
  name: string
  type: ArtifactType
  content: string
  metadata?: Record<string, any>
  parentId?: string
  tags?: string[]
}

export interface ArtifactUpdateInput {
  name?: string
  content?: string
  metadata?: Record<string, any>
  pinned?: boolean
  tags?: string[]
}

export interface ArtifactFilter {
  type?: ArtifactType
  pinned?: boolean
  tag?: string
  parentId?: string
  createdBy?: string
  limit?: number
  offset?: number
}

export interface ArtifactStats {
  total: number
  byType: Record<ArtifactType, number>
  recentCount: number
  pinnedCount: number
}
