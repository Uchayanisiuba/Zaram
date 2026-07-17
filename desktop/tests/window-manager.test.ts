import { describe, it, expect, vi } from 'vitest'
import { WindowManager } from '../src/main/window-manager'
import path from 'path'
import fs from 'fs'

vi.mock('electron', () => ({
  app: {
    isPackaged: false
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
      openDevTools: vi.fn()
    }
  })),
  screen: {
    getPrimaryDisplay: () => ({
      workAreaSize: { width: 1920, height: 1080 }
    })
  }
}))

describe('WindowManager', () => {
  it('should create with default state', () => {
    const manager = new WindowManager('/tmp')
    const state = manager.getWindowState()
    expect(state.width).toBe(1200)
    expect(state.height).toBe(800)
    expect(state.isMaximized).toBe(false)
  })

  it('should create main window', () => {
    const manager = new WindowManager('/tmp')
    const window = manager.createMainWindow()
    expect(window).toBeDefined()
  })

  it('should create splash window', () => {
    const manager = new WindowManager('/tmp')
    const splash = manager.createSplashWindow()
    expect(splash).toBeDefined()
  })

  it('should return null when no main window exists', () => {
    const manager = new WindowManager('/tmp')
    expect(manager.getMainWindow()).toBeNull()
  })
})
