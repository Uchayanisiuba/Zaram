import { ipcMain, shell } from 'electron'
import { ShellService } from './desktop-service'

export class ShellServiceImpl implements ShellService {
  async initialize(): Promise<void> {
    ipcMain.handle('shell:open-external', async (_event, url: string) => {
      try {
        await shell.openExternal(url)
        return { success: true }
      } catch (error) {
        return { success: false, error: String(error) }
      }
    })

    ipcMain.handle('shell:open-path', async (_event, filePath: string) => {
      try {
        await shell.openPath(filePath)
        return { success: true }
      } catch (error) {
        return { success: false, error: String(error) }
      }
    })
  }

  async shutdown(): Promise<void> {
    // No cleanup needed
  }

  async openExternal(url: string) {
    return { success: false, error: 'Not implemented' }
  }

  async openPath(filePath: string) {
    return { success: false, error: 'Not implemented' }
  }
}
