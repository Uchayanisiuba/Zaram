// desktop/src/runtime/capabilities/filesystem/types.ts
//
// Milestone 1.7 — Filesystem Capability Pack types.
//
// Pure type contracts for the filesystem capability pack. No behaviour,
// no side effects, no forbidden imports.

// --- Permissions -----------------------------------------------------------

export type FileSystemPermission =
  | 'read'
  | 'write'
  | 'delete'
  | 'execute'
  | 'admin'

// --- Inputs ----------------------------------------------------------------

export interface ReadFileInput {
  path: string
  encoding?: BufferEncoding
}

export interface WriteFileInput {
  path: string
  content: string
  encoding?: BufferEncoding
  append?: boolean
}

export interface CreateFileInput {
  path: string
  content?: string
}

export interface DeleteFileInput {
  path: string
}

export interface RenameFileInput {
  oldPath: string
  newPath: string
}

export interface MoveFileInput {
  sourcePath: string
  destinationPath: string
}

export interface CopyFileInput {
  sourcePath: string
  destinationPath: string
}

export interface CreateFolderInput {
  path: string
  recursive?: boolean
}

export interface DeleteFolderInput {
  path: string
  recursive?: boolean
}

export interface SearchFilesInput {
  rootPath: string
  query: string
  maxResults?: number
}

export interface ListDirectoryInput {
  path: string
}

export interface FileMetadataInput {
  path: string
}

export interface CompressFolderInput {
  sourcePath: string
  destinationPath: string
}

export interface ExtractArchiveInput {
  archivePath: string
  destinationPath: string
}

export interface ExistsInput {
  path: string
}

// --- Outputs ---------------------------------------------------------------

export interface FileSystemSuccess<T = unknown> {
  success: true
  data: T
  audit: FileSystemAudit
}

export interface FileSystemFailure {
  success: false
  error: { code: string; message: string }
  audit: FileSystemAudit
}

export type FileSystemResult<T = unknown> = FileSystemSuccess<T> | FileSystemFailure

export interface FileSystemAudit {
  capability: string
  path: string
  action: string
  timestamp: number
  durationMs: number
  actor?: string
  correlationId?: string
}

// --- File info -------------------------------------------------------------

export interface FileInfo {
  path: string
  name: string
  extension: string
  size: number
  isDirectory: boolean
  isFile: boolean
  createdAt: number
  modifiedAt: number
  accessedAt: number
  permissions: string
}

export interface DirectoryListing {
  path: string
  entries: FileInfo[]
  total: number
}

export interface SearchResult {
  path: string
  name: string
  match: string
  score: number
}

export interface SearchResults {
  query: string
  results: SearchResult[]
  total: number
}

// --- Permission rules ------------------------------------------------------

export interface PermissionRule {
  pathPattern: string
  permissions: FileSystemPermission[]
  effect: 'allow' | 'deny'
}

export interface PermissionContext {
  grantedPermissions: string[]
  rules?: PermissionRule[]
  workspaceRoot?: string
}

// --- Capability pack contract ----------------------------------------------

export interface ICapabilityPack {
  registerHandlers(invoker: import('../../execution').IExecutionInvoker): void
  registerDescriptors(capabilityRuntime: import('../../capability').ICapabilityRuntime): void
}

// Re-imported here so the pack can depend on the contract without importing
// the concrete execution module.

export type { ExecutionHandler, ExecutionRollback } from '../../execution'
