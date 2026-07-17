import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AppLifecycle } from '../src/main/lifecycle'

vi.mock('electron', () => ({
  app: {
    setAppUserModelId: vi.fn(),
    on: vi.fn(),
    whenReady: () => Promise.resolve(),
    getPath: (name: string) => `/tmp/${name}`
  },
  BrowserWindow: vi.fn().mockImplementation(() => ({
    on: vi.fn(),
    once: vi.fn(),
    loadFile: vi.fn(),
    loadURL: vi.fn(),
    show: vi.fn(),
    maximize: vi.fn(),
    minimize: vi.fn(),
    restore: vi.fn(),
    isMinimized: vi.fn(() => false),
    isMaximized: vi.fn(() => false),
    getSize: vi.fn(() => [1200, 800]),
    getPosition: vi.fn(() => [100, 100]),
    destroy: vi.fn(),
    isDestroyed: vi.fn(() => false),
    close: vi.fn(),
    webContents: {
      openDevTools: vi.fn(),
      send: vi.fn()
    }
  })),
  ipcMain: {
    handle: vi.fn(),
    on: vi.fn()
  },
  screen: {
    getPrimaryDisplay: () => ({ scaleFactor: 1 })
  }
}))

describe('AppLifecycle', () => {
  let lifecycle: AppLifecycle

  beforeEach(() => {
    lifecycle = new AppLifecycle()
    vi.clearAllMocks()
  })

  it('should initialize without errors', async () => {
    await expect(lifecycle.initialize()).resolves.toBeUndefined()
  })

  it('should provide window manager', () => {
    const windowManager = lifecycle.getWindowManager()
    expect(windowManager).toBeDefined()
  })

  it('should provide backend service', () => {
    const backendService = lifecycle.getBackendService()
    expect(backendService).toBeDefined()
  })
})
