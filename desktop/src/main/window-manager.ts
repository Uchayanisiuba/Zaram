import { BrowserWindow, screen, ipcMain } from 'electron'
import path from 'path'
import fs from 'fs'
import { getSplashPath, isDevelopment } from '../config/paths'

export interface WindowState {
  width: number
  height: number
  x?: number
  y?: number
  isMaximized: boolean
}

const DEFAULT_WINDOW_STATE: WindowState = {
  width: 1200,
  height: 800,
  isMaximized: false
}

const STATE_FILE = 'window-state.json'

export class WindowManager {
  private mainWindow: BrowserWindow | null = null
  private splashWindow: BrowserWindow | null = null
  private state: WindowState = { ...DEFAULT_WINDOW_STATE }
  private statePath: string

  constructor(private appDataPath: string) {
    this.statePath = path.join(this.appDataPath, STATE_FILE)
    this.loadState()
  }

  createMainWindow(): BrowserWindow {
    const windowState = this.getWindowState()

    this.mainWindow = new BrowserWindow({
      width: windowState.width,
      height: windowState.height,
      x: windowState.x,
      y: windowState.y,
      minWidth: 800,
      minHeight: 600,
      show: false,
      title: 'Zaram',
      backgroundColor: '#0a0a0f',
      webPreferences: {
        preload: path.join(__dirname, '..', 'preload', 'index.js'),
        contextIsolation: true,
        sandbox: false,
        nodeIntegration: false,
        webSecurity: true
      }
    })

    this.mainWindow.on('maximize', () => {
      this.state.isMaximized = true
      this.saveState()
    })

    this.mainWindow.on('unmaximize', () => {
      this.state.isMaximized = false
      this.saveState()
    })

    this.mainWindow.on('resize', () => {
      if (!this.state.isMaximized && this.mainWindow) {
        const [width, height] = this.mainWindow.getSize()
        this.state.width = width
        this.state.height = height
        this.saveState()
      }
    })

    this.mainWindow.on('move', () => {
      if (!this.state.isMaximized && this.mainWindow) {
        const [x, y] = this.mainWindow.getPosition()
        this.state.x = x
        this.state.y = y
        this.saveState()
      }
    })

    this.mainWindow.on('closed', () => {
      this.mainWindow = null
    })

    if (this.state.isMaximized) {
      this.mainWindow.maximize()
    }

    return this.mainWindow
  }

  createSplashWindow(): BrowserWindow {
    this.splashWindow = new BrowserWindow({
      width: 400,
      height: 300,
      center: true,
      frame: false,
      alwaysOnTop: true,
      resizable: false,
      backgroundColor: '#0a0a0f',
      webPreferences: {
        preload: path.join(__dirname, '..', 'preload', 'index.js'),
        contextIsolation: true,
        sandbox: false,
        nodeIntegration: false,
        webSecurity: true
      }
    })

    const splashPath = getSplashPath()
    if (fs.existsSync(splashPath)) {
      this.splashWindow.loadFile(splashPath)
    } else {
      this.splashWindow.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(`
        <html>
          <head>
            <style>
              body {
                margin: 0;
                padding: 0;
                background: #0a0a0f;
                color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100vh;
              }
              .logo {
                font-size: 48px;
                font-weight: bold;
                margin-bottom: 20px;
              }
              .loader {
                width: 40px;
                height: 40px;
                border: 3px solid #333;
                border-top-color: #7c3aed;
                border-radius: 50%;
                animation: spin 1s linear infinite;
              }
              @keyframes spin {
                to { transform: rotate(360deg); }
              }
            </style>
          </head>
          <body>
            <div class="logo">Zaram</div>
            <div class="loader"></div>
          </body>
        </html>
      `))
    }

    return this.splashWindow
  }

  closeSplash(): void {
    if (this.splashWindow && !this.splashWindow.isDestroyed()) {
      this.splashWindow.close()
      this.splashWindow = null
    }
  }

  getMainWindow(): BrowserWindow | null {
    return this.mainWindow
  }

  getWindowState(): WindowState {
    return { ...this.state }
  }

  private loadState(): void {
    try {
      if (fs.existsSync(this.statePath)) {
        const data = fs.readFileSync(this.statePath, 'utf-8')
        const loaded = JSON.parse(data) as WindowState
        this.state = { ...DEFAULT_WINDOW_STATE, ...loaded }
      }
    } catch (error) {
      console.error('Failed to load window state:', error)
    }
  }

  private saveState(): void {
    try {
      fs.writeFileSync(this.statePath, JSON.stringify(this.state, null, 2), 'utf-8')
    } catch (error) {
      console.error('Failed to save window state:', error)
    }
  }

  maximize(): void {
    this.mainWindow?.maximize()
  }

  minimize(): void {
    this.mainWindow?.minimize()
  }

  restore(): void {
    if (this.mainWindow?.isMinimized()) {
      this.mainWindow.restore()
    }
    if (this.mainWindow?.isMaximized()) {
      this.mainWindow.unmaximize()
    }
  }

  isMaximized(): boolean {
    return this.mainWindow?.isMaximized() ?? false
  }

  destroy(): void {
    this.closeSplash()
    this.mainWindow?.destroy()
    this.mainWindow = null
  }
}
