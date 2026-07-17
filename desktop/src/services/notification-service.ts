import { ipcMain } from 'electron'
import { NotificationService } from './desktop-service'

export class NotificationServiceImpl implements NotificationService {
  async initialize(): Promise<void> {
    ipcMain.handle('notification:show', async (_event, title: string, body: string) => {
      try {
        const { Notification } = require('electron')
        if (Notification.isSupported()) {
          return new Promise((resolve) => {
            const notification = new Notification({ title, body })
            notification.on('click', () => resolve({ success: true, clicked: true }))
            notification.on('close', () => resolve({ success: true, clicked: false }))
            notification.on('failed', () => resolve({ success: false, error: 'Notification failed' }))
            notification.show()
          })
        }
        return { success: false, error: 'Notifications not supported' }
      } catch (error) {
        return { success: false, error: String(error) }
      }
    })
  }

  async shutdown(): Promise<void> {
    // No cleanup needed
  }

  async show(title: string, body: string) {
    return { success: false, error: 'Not implemented' }
  }
}
