// desktop/src/capabilities/filesystem/filesystem-trash.ts
//
// Milestone 2.0 — Platform-aware recycle bin / trash.
//
// Never permanently deletes. Uses platform trash when available,
// otherwise falls back to .zaram_trash inside the workspace.

import { execSync } from 'child_process'
import { existsSync, mkdirSync, statSync, renameSync, unlinkSync, readdirSync, writeFileSync } from 'fs'
import { join, basename, dirname, extname } from 'path'
import type { WorkspaceConfig } from './filesystem-paths'

export interface TrashResult {
  trashed: boolean
  path: string
  reason?: string
}

export function trashFile(filePath: string, config: WorkspaceConfig): TrashResult {
  if (!existsSync(filePath)) {
    return { trashed: false, path: filePath, reason: 'File does not exist' }
  }

  const platformTrash = tryPlatformTrash(filePath)
  if (platformTrash.trashed) {
    return platformTrash
  }

  return fallbackTrash(filePath, config)
}

function tryPlatformTrash(filePath: string): TrashResult {
  try {
    const platform = process.platform
    if (platform === 'win32') {
      return windowsRecycleBin(filePath)
    }
    if (platform === 'darwin') {
      return macTrash(filePath)
    }
    return linuxTrash(filePath)
  } catch {
    return { trashed: false, path: filePath }
  }
}

function windowsRecycleBin(filePath: string): TrashResult {
  try {
    const psScript = `
      Add-Type -AssemblyName Microsoft.VisualBasic
      $path = '${filePath.replace(/'/g, "''")}'
      [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($path, 'OnlyErrorDialogs', 'SendToRecycleBin')
    `
    execSync(`powershell -NoProfile -Command "${psScript.replace(/"/g, '\\"')}"`, {
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe']
    })
    return { trashed: true, path: filePath }
  } catch {
    return { trashed: false, path: filePath }
  }
}

function macTrash(filePath: string): TrashResult {
  try {
    const escaped = filePath.replace(/'/g, "\\'")
    execSync(`osascript -e 'tell application "Finder" to delete (POSIX file "${escaped}")'`, {
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe']
    })
    return { trashed: true, path: filePath }
  } catch {
    return { trashed: false, path: filePath }
  }
}

function linuxTrash(filePath: string): TrashResult {
  const commands = [
    ['gio', 'trash', filePath],
    ['kioclient5', 'move', filePath, 'trash:/'],
    ['trash-put', filePath],
    ['trash', filePath]
  ]
  for (const [cmd, ...args] of commands) {
    try {
      execSync([cmd, ...args].map((a) => `"${a}"`).join(' '), {
        encoding: 'utf8',
        stdio: ['pipe', 'pipe', 'pipe']
      })
      return { trashed: true, path: filePath }
    } catch {
      // try next
    }
  }
  return { trashed: false, path: filePath }
}

function fallbackTrash(filePath: string, config: WorkspaceConfig): TrashResult {
  try {
    if (!existsSync(config.trashDir)) {
      mkdirSync(config.trashDir, { recursive: true })
    }

    const base = basename(filePath)
    const ext = extname(base)
    const name = base.slice(0, -ext.length)
    const timestamp = Date.now()
    const trashPath = join(config.trashDir, `${name}_${timestamp}${ext}`)

    renameSync(filePath, trashPath)

    const metaPath = trashPath + '.meta'
    const meta = {
      originalPath: filePath,
      trashedAt: timestamp,
      platform: process.platform
    }
    writeFileSync(metaPath, JSON.stringify(meta, null, 2), 'utf-8')

    return { trashed: true, path: trashPath }
  } catch (error) {
    return { trashed: false, path: filePath, reason: String(error) }
  }
}
