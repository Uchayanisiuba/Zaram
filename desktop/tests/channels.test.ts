import { describe, it, expect, vi } from 'vitest'
import { DESKTOP_CHANNELS } from '../src/ipc/channels'

describe('IPC Channels', () => {
  it('should have all required channels defined', () => {
    expect(DESKTOP_CHANNELS.WINDOW).toBe('window')
    expect(DESKTOP_CHANNELS.NOTIFICATION).toBe('notification')
    expect(DESKTOP_CHANNELS.SHELL).toBe('shell')
    expect(DESKTOP_CHANNELS.FILE_DIALOG).toBe('file-dialog')
    expect(DESKTOP_CHANNELS.DOWNLOAD).toBe('download')
    expect(DESKTOP_CHANNELS.SETTINGS).toBe('settings')
    expect(DESKTOP_CHANNELS.BACKEND).toBe('backend')
    expect(DESKTOP_CHANNELS.CLIPBOARD).toBe('clipboard')
    expect(DESKTOP_CHANNELS.SYSTEM).toBe('system')
  })

  it('should have unique channel names', () => {
    const values = Object.values(DESKTOP_CHANNELS)
    const unique = new Set(values)
    expect(unique.size).toBe(values.length)
  })
})
