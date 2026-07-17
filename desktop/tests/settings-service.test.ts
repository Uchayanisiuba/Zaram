import { describe, it, expect, vi } from 'vitest'
import os from 'os'
import path from 'path'

vi.mock('electron', () => ({
  app: {
    getPath: (name: string) => path.join(os.tmpdir(), name)
  }
}))

import { SettingsServiceImpl } from '../src/services/settings-service'

describe('SettingsService', () => {
  it('should return null for missing keys', async () => {
    const service = new SettingsServiceImpl()
    const result = await service.get('nonexistent')
    expect(result).toBeNull()
  })

  it('should return default value for missing keys', async () => {
    const service = new SettingsServiceImpl()
    const result = await service.get('nonexistent', 'default')
    expect(result).toBe('default')
  })

  it('should set and get values', async () => {
    const service = new SettingsServiceImpl()
    await service.set('testKey', 'testValue')
    const result = await service.get('testKey')
    expect(result).toBe('testValue')
  })

  it('should return success for set operations', async () => {
    const service = new SettingsServiceImpl()
    const result = await service.set('testKey', { nested: true })
    expect(result.success).toBe(true)
  })
})
