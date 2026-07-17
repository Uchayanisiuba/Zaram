import { ipcMain } from 'electron'
import path from 'path'
import { BackendService } from '../services/backend-service'

export class IpcBridge {
  private backendService: BackendService

  constructor(backendService: BackendService) {
    this.backendService = backendService
    this.registerHandlers()
  }

  private registerHandlers(): void {
    ipcMain.handle('backend:health', async () => {
      const healthy = await this.backendService.checkHealth()
      return { healthy }
    })

    ipcMain.handle('backend:status', () => {
      return this.backendService.getStatus()
    })

    ipcMain.handle('notification:show', async (_event, title: string, body: string) => {
      const { Notification } = require('electron')
      if (Notification.isSupported()) {
        const notification = new Notification({ title, body })
        notification.show()
        return { success: true }
      }
      return { success: false, error: 'Notifications not supported' }
    })

    ipcMain.handle('shell:open-external', async (_event, url: string) => {
      const { shell } = require('electron')
      shell.openExternal(url)
      return { success: true }
    })

    ipcMain.handle('shell:open-path', async (_event, filePath: string) => {
      const { shell } = require('electron')
      shell.openPath(filePath)
      return { success: true }
    })

    ipcMain.handle('clipboard:read-text', async () => {
      const { clipboard } = require('electron')
      return clipboard.readText()
    })

    ipcMain.handle('clipboard:write-text', async (_event, text: string) => {
      const { clipboard } = require('electron')
      clipboard.writeText(text)
      return { success: true }
    })

    ipcMain.handle('system:platform', () => {
      return process.platform
    })

    ipcMain.handle('system:version', () => {
      return process.version
    })

    ipcMain.handle('system:arch', () => {
      return process.arch
    })

    ipcMain.handle('settings:get', async (_event, key: string) => {
      const { app } = require('electron')
      const storePath = path.join(app.getPath('userData'), 'settings.json')
      const fs = require('fs')
      try {
        if (fs.existsSync(storePath)) {
          const data = JSON.parse(fs.readFileSync(storePath, 'utf-8'))
          return data[key]
        }
      } catch {
        // ignore
      }
      return null
    })

    ipcMain.handle('settings:set', async (_event, key: string, value: any) => {
      const { app } = require('electron')
      const storePath = path.join(app.getPath('userData'), 'settings.json')
      const fs = require('fs')
      try {
        let data: Record<string, any> = {}
        if (fs.existsSync(storePath)) {
          data = JSON.parse(fs.readFileSync(storePath, 'utf-8'))
        }
        data[key] = value
        fs.writeFileSync(storePath, JSON.stringify(data, null, 2), 'utf-8')
        return { success: true }
      } catch (error) {
        return { success: false, error: String(error) }
      }
    })
  }

  cleanup(): void {
    // Remove all registered IPC handlers if needed
  }
}
