import { ipcMain } from 'electron'
import { WindowManager } from '../main/window-manager'
import { WindowService } from './desktop-service'

export class WindowServiceImpl implements WindowService {
  constructor(private windowManager: WindowManager) {}

  async initialize(): Promise<void> {
    ipcMain.handle('window:maximize', () => this.maximize())
    ipcMain.handle('window:minimize', () => this.minimize())
    ipcMain.handle('window:restore', () => this.restore())
    ipcMain.handle('window:is-maximized', () => this.isMaximized())
    ipcMain.handle('window:get-state', () => this.getState())
  }

  async shutdown(): Promise<void> {
    // No cleanup needed
  }

  maximize(): void {
    this.windowManager.maximize()
  }

  minimize(): void {
    this.windowManager.minimize()
  }

  restore(): void {
    this.windowManager.restore()
  }

  isMaximized(): boolean {
    return this.windowManager.isMaximized()
  }

  getState() {
    return this.windowManager.getWindowState()
  }
}
