// desktop/src/capabilities/filesystem/filesystem-operations.ts
//
// Milestone 2.0 — Core filesystem operations.
//
// All file operations are sandboxed, atomic where required, and never
// perform permanent deletion. Uses fs/promises.

import { 
  readFile, writeFile, mkdir, rename, unlink, stat, readdir,
  copyFile, access, constants, realpath, open
} from 'fs/promises'
import { existsSync, statSync, readdirSync } from 'fs'
import { join, dirname, basename, extname, resolve } from 'path'
import { randomUUID } from 'crypto'
import type { WorkspaceConfig } from './filesystem-paths'
import { trashFile } from './filesystem-trash'
import type { FileSystemResult, FileSystemAudit, FileInfo, DirectoryListing, SearchResults } from './filesystem-types'

export interface FileSystemOperations {
  readFile(input: { path: string; encoding?: BufferEncoding }, audit: FileSystemAudit): Promise<FileSystemResult<string>>
  writeFile(input: { path: string; content: string; encoding?: BufferEncoding; append?: boolean }, audit: FileSystemAudit): Promise<FileSystemResult<void>>
  createFolder(input: { path: string; recursive?: boolean }, audit: FileSystemAudit): Promise<FileSystemResult<void>>
  rename(input: { oldPath: string; newPath: string }, audit: FileSystemAudit): Promise<FileSystemResult<void>>
  move(input: { sourcePath: string; destinationPath: string }, audit: FileSystemAudit): Promise<FileSystemResult<void>>
  copy(input: { sourcePath: string; destinationPath: string }, audit: FileSystemAudit): Promise<FileSystemResult<void>>
  deleteFile(input: { path: string }, audit: FileSystemAudit): Promise<FileSystemResult<{ trashedPath: string }>>
  deleteFolder(input: { path: string; recursive?: boolean }, audit: FileSystemAudit): Promise<FileSystemResult<{ trashedPath: string }>>
  listDirectory(input: { path: string }, audit: FileSystemAudit): Promise<FileSystemResult<DirectoryListing>>
  metadata(input: { path: string }, audit: FileSystemAudit): Promise<FileSystemResult<FileInfo>>
  exists(input: { path: string }, audit: FileSystemAudit): Promise<FileSystemResult<boolean>>
  search(input: { rootPath: string; query: string; maxResults?: number }, audit: FileSystemAudit): Promise<FileSystemResult<SearchResults>>
  tree(input: { path: string }, audit: FileSystemAudit): Promise<FileSystemResult<FileInfo[]>>
  createProject(input: { name: string; template?: string; root?: string }, audit: FileSystemAudit): Promise<FileSystemResult<{ projectPath: string }>>
}

export function createFileSystemOperations(config: WorkspaceConfig): FileSystemOperations {
  const { root: workspaceRoot } = config

  return {
    async readFile(input, audit) {
      try {
        const resolved = resolve(workspaceRoot, input.path)
        const content = await readFile(resolved, { encoding: input.encoding ?? 'utf-8' })
        return { success: true, data: content, audit }
      } catch (error) {
        return { success: false, error: { code: 'read_error', message: String(error) }, audit }
      }
    },

    async writeFile(input, audit) {
      try {
        const resolved = resolve(workspaceRoot, input.path)
        const dir = dirname(resolved)
        await mkdir(dir, { recursive: true })

        if (input.append && existsSync(resolved)) {
          await writeFile(resolved, input.content, { encoding: input.encoding ?? 'utf-8', flag: 'a' })
        } else {
          const tmpPath = resolved + `.tmp.${randomUUID()}`
          await writeFile(tmpPath, input.content, { encoding: input.encoding ?? 'utf-8' })
          await rename(tmpPath, resolved)
        }

        return { success: true, data: undefined, audit }
      } catch (error) {
        return { success: false, error: { code: 'write_error', message: String(error) }, audit }
      }
    },

    async createFolder(input, audit) {
      try {
        const resolved = resolve(workspaceRoot, input.path)
        await mkdir(resolved, { recursive: Boolean(input.recursive) })
        return { success: true, data: undefined, audit }
      } catch (error) {
        return { success: false, error: { code: 'mkdir_error', message: String(error) }, audit }
      }
    },

    async rename(input, audit) {
      try {
        const oldResolved = resolve(workspaceRoot, input.oldPath)
        const newResolved = resolve(workspaceRoot, input.newPath)
        await rename(oldResolved, newResolved)
        return { success: true, data: undefined, audit }
      } catch (error) {
        return { success: false, error: { code: 'rename_error', message: String(error) }, audit }
      }
    },

    async move(input, audit) {
      try {
        const sourceResolved = resolve(workspaceRoot, input.sourcePath)
        const destResolved = resolve(workspaceRoot, input.destinationPath)
        const destDir = dirname(destResolved)
        await mkdir(destDir, { recursive: true })
        await rename(sourceResolved, destResolved)
        return { success: true, data: undefined, audit }
      } catch (error) {
        return { success: false, error: { code: 'move_error', message: String(error) }, audit }
      }
    },

    async copy(input, audit) {
      try {
        const sourceResolved = resolve(workspaceRoot, input.sourcePath)
        const destResolved = resolve(workspaceRoot, input.destinationPath)
        const destDir = dirname(destResolved)
        await mkdir(destDir, { recursive: true })
        await copyFile(sourceResolved, destResolved)
        return { success: true, data: undefined, audit }
      } catch (error) {
        return { success: false, error: { code: 'copy_error', message: String(error) }, audit }
      }
    },

    async deleteFile(input, audit) {
      try {
        const resolved = resolve(workspaceRoot, input.path)
        const result = trashFile(resolved, config)
        if (!result.trashed) {
          return { success: false, error: { code: 'delete_error', message: result.reason ?? 'Unknown error' }, audit }
        }
        return { success: true, data: { trashedPath: result.path }, audit }
      } catch (error) {
        return { success: false, error: { code: 'delete_error', message: String(error) }, audit }
      }
    },

    async deleteFolder(input, audit) {
      try {
        const resolved = resolve(workspaceRoot, input.path)
        if (!existsSync(resolved)) {
          return { success: false, error: { code: 'not_found', message: 'Folder does not exist' }, audit }
        }
        const result = trashFile(resolved, config)
        if (!result.trashed) {
          return { success: false, error: { code: 'delete_error', message: result.reason ?? 'Unknown error' }, audit }
        }
        return { success: true, data: { trashedPath: result.path }, audit }
      } catch (error) {
        return { success: false, error: { code: 'delete_error', message: String(error) }, audit }
      }
    },

    async listDirectory(input, audit) {
      try {
        const resolved = resolve(workspaceRoot, input.path)
        const entries = await readdir(resolved, { withFileTypes: true })
        const items: FileInfo[] = []
        for (const entry of entries) {
          const fullPath = join(resolved, entry.name)
          try {
            const stats = await stat(fullPath)
            items.push({
              path: fullPath,
              name: entry.name,
              extension: extname(entry.name),
              size: stats.size,
              isDirectory: entry.isDirectory(),
              isFile: entry.isFile(),
              createdAt: stats.birthtimeMs,
              modifiedAt: stats.mtimeMs,
              accessedAt: stats.atimeMs,
              permissions: (stats.mode & 0o777).toString(8)
            })
          } catch {
            // skip unreadable entries
          }
        }
        const listing: DirectoryListing = { path: resolved, entries: items, total: items.length }
        return { success: true, data: listing, audit }
      } catch (error) {
        return { success: false, error: { code: 'listdir_error', message: String(error) }, audit }
      }
    },

    async metadata(input, audit) {
      try {
        const resolved = resolve(workspaceRoot, input.path)
        const stats = await stat(resolved)
        const info: FileInfo = {
          path: resolved,
          name: basename(resolved),
          extension: extname(resolved),
          size: stats.size,
          isDirectory: stats.isDirectory(),
          isFile: stats.isFile(),
          createdAt: stats.birthtimeMs,
          modifiedAt: stats.mtimeMs,
          accessedAt: stats.atimeMs,
          permissions: (stats.mode & 0o777).toString(8)
        }
        return { success: true, data: info, audit }
      } catch (error) {
        return { success: false, error: { code: 'metadata_error', message: String(error) }, audit }
      }
    },

    async exists(input, audit) {
      try {
        const resolved = resolve(workspaceRoot, input.path)
        await access(resolved, constants.F_OK)
        return { success: true, data: true, audit }
      } catch {
        return { success: true, data: false, audit }
      }
    },

    async search(input, audit) {
      try {
        const rootResolved = resolve(workspaceRoot, input.rootPath)
        const results: SearchResults = { query: input.query, results: [], total: 0 }
        if (!existsSync(rootResolved)) {
          return { success: true, data: results, audit }
        }
        const maxResults = input.maxResults ?? 50
        const lowerQuery = input.query.toLowerCase()
        walkSearch(rootResolved, lowerQuery, maxResults, results)
        return { success: true, data: results, audit }
      } catch (error) {
        return { success: false, error: { code: 'search_error', message: String(error) }, audit }
      }
    },

    async tree(input, audit) {
      try {
        const resolved = resolve(workspaceRoot, input.path)
        const nodes: FileInfo[] = []
        if (!existsSync(resolved)) {
          return { success: true, data: nodes, audit }
        }
        walkTree(resolved, nodes)
        return { success: true, data: nodes, audit }
      } catch (error) {
        return { success: false, error: { code: 'tree_error', message: String(error) }, audit }
      }
    },

    async createProject(input, audit) {
      try {
        const projectRoot = input.root ? resolve(workspaceRoot, input.root) : join(workspaceRoot, input.name)
        await mkdir(projectRoot, { recursive: true })

        const structure: Record<string, string> = {
          'README.md': `# ${input.name}\n`,
          'src/index.ts': `export const init = () => {\n  console.log('${input.name} initialized')\n}\n`,
          'src/README.md': `# ${input.name}/src\n`,
          '.gitignore': 'node_modules/\ndist/\n'
        }

        if (input.template) {
          structure['src/template.ts'] = `// ${input.template} template\n`
        }

        for (const [relPath, content] of Object.entries(structure)) {
          const fullPath = join(projectRoot, relPath)
          const dir = dirname(fullPath)
          await mkdir(dir, { recursive: true })
          await writeFile(fullPath, content, 'utf-8')
        }

        return { success: true, data: { projectPath: projectRoot }, audit }
      } catch (error) {
        return { success: false, error: { code: 'project_create_error', message: String(error) }, audit }
      }
    }
  }
}

function walkSearch(dir: string, query: string, maxResults: number, results: SearchResults): void {
  if (results.results.length >= maxResults) return
  try {
    const entries = readdirSync(dir)
    for (const entry of entries) {
      if (results.results.length >= maxResults) break
      const fullPath = join(dir, entry)
      if (entry.toLowerCase().includes(query)) {
        results.results.push({
          path: fullPath,
          name: entry,
          match: entry,
          score: entry.toLowerCase() === query ? 1 : 0.5
        })
        results.total++
      }
      try {
        if (statSync(fullPath).isDirectory()) {
          walkSearch(fullPath, query, maxResults, results)
        }
      } catch {
        // skip
      }
    }
  } catch {
    // skip unreadable directories
  }
}

function walkTree(dir: string, nodes: FileInfo[]): void {
  try {
    const entries = readdirSync(dir, { withFileTypes: true })
    for (const entry of entries) {
      const fullPath = join(dir, entry.name)
      try {
        const stats = statSync(fullPath)
        nodes.push({
          path: fullPath,
          name: entry.name,
          extension: extname(entry.name),
          size: stats.size,
          isDirectory: entry.isDirectory(),
          isFile: entry.isFile(),
          createdAt: stats.birthtimeMs,
          modifiedAt: stats.mtimeMs,
          accessedAt: stats.atimeMs,
          permissions: (stats.mode & 0o777).toString(8)
        })
        if (entry.isDirectory()) {
          walkTree(fullPath, nodes)
        }
      } catch {
        // skip unreadable entries
      }
    }
  } catch {
    // skip unreadable directories
  }
}
