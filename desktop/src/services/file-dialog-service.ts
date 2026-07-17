import { ipcMain, dialog } from 'electron'
import { FileDialogService } from './desktop-service'

export class FileDialogServiceImpl implements FileDialogService {
  async initialize(): Promise<void> {
    ipcMain.handle('file-dialog:open', async (_event, options: any) => {
      try {
        const result = await dialog.showOpenDialog(options)
        return {
          success: !result.canceled,
          filePaths: result.filePaths,
          canceled: result.canceled
        }
      } catch (error) {
        return { success: false, error: String(error) }
      }
    })

    ipcMain.handle('file-dialog:save', async (_event, options: any) => {
      try {
        const result = await dialog.showSaveDialog(options)
        return {
          success: !result.canceled,
          filePath: result.filePath,
          canceled: result.canceled
        }
      } catch (error) {
        return { success: false, error: String(error) }
      }
    })

    ipcMain.handle('file-dialog:select-directory', async (_event, options: any) => {
      try {
        const result = await dialog.showOpenDialog({
          ...options,
          properties: ['openDirectory']
        })
        return {
          success: !result.canceled,
          filePaths: result.filePaths,
          canceled: result.canceled
        }
      } catch (error) {
        return { success: false, error: String(error) }
      }
    })
  }

  async shutdown(): Promise<void> {
    // No cleanup needed
  }

  async openFile(options?: any) {
    return { success: false, error: 'Not implemented' }
  }

  async saveFile(options?: any) {
    return { success: false, error: 'Not implemented' }
  }

  async selectDirectory(options?: any) {
    return { success: false, error: 'Not implemented' }
  }
}
