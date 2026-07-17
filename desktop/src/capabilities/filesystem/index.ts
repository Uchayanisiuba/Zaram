// desktop/src/capabilities/filesystem/index.ts
//
// Milestone 2.0 — Filesystem Capability Pack barrel.
//
// The Filesystem Capability Pack is the first concrete capability executed
// through the completed Executive -> Capability -> Execution pipeline.
// It exposes handlers only; the Execution Runtime is the sole execution
// authority. It does not import the drawing layer, the body layer, concrete
// avatars, the character projection, the animation engine, frame snapshots,
// the orb drawing code, the desktop shell, any GPU/3D engine, or the
// Emotion/Behaviour/Presence/Character/body-layer runtimes.

export { FilesystemCapabilityPack, buildFilesystemRollback } from './filesystem-capability'
export type { FilesystemHandlerContext } from './filesystem-handler'
export { createFilesystemHandlers, buildAudit } from './filesystem-handler'
export {
  handleRead,
  handleWrite,
  handleDelete,
  handleCreateFolder,
  handleRename,
  handleMove,
  handleCopy,
  handleListDirectory,
  handleMetadata,
  handleExists,
  handleSearch,
  handleTree,
  handleCreateProject
} from './filesystem-handler'
export { FileSystemPermissionManager } from './filesystem-permissions'
export { validatePathSecurity, assertPathSafe } from './filesystem-security'
export { buildWorkspaceConfig, canonicalizePath, isSystemPath, containsGitSegment, resolveWorkspaceRoot } from './filesystem-paths'
export { createFileSystemOperations } from './filesystem-operations'
export { trashFile } from './filesystem-trash'
export type {
  FileSystemPermission,
  PermissionLevel,
  ReadFileInput,
  WriteFileInput,
  CreateFileInput,
  DeleteFileInput,
  RenameFileInput,
  MoveFileInput,
  CopyFileInput,
  CreateFolderInput,
  DeleteFolderInput,
  SearchFilesInput,
  ListDirectoryInput,
  FileMetadataInput,
  CompressFolderInput,
  ExtractArchiveInput,
  ExistsInput,
  CreateProjectInput,
  FileSystemSuccess,
  FileSystemFailure,
  FileSystemResult,
  FileSystemAudit,
  FileInfo,
  DirectoryListing,
  SearchResult,
  SearchResults,
  PermissionRule,
  PermissionContext,
  ICapabilityPack,
  FileSystemEventType,
  FileSystemEvent
} from './filesystem-types'
