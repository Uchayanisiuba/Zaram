import { describe, it, expect, vi } from 'vitest'

vi.mock('electron', () => ({
  app: {
    isPackaged: false,
    getPath: (name: string) => `/tmp/${name}`
  }
}))

import { BackendService } from '../src/services/backend-service'

describe('BackendService', () => {
  it('should initialize with default options', () => {
    const service = new BackendService()
    const status = service.getStatus()
    expect(status.host).toBe('127.0.0.1')
    expect(status.port).toBe(8000)
    expect(status.running).toBe(false)
  })

  it('should initialize with custom options', () => {
    const service = new BackendService({
      host: 'localhost',
      port: 9000
    })
    const status = service.getStatus()
    expect(status.host).toBe('localhost')
    expect(status.port).toBe(9000)
  })

  it('should provide status object', () => {
    const service = new BackendService()
    const status = service.getStatus()
    expect(status).toHaveProperty('running')
    expect(status).toHaveProperty('host')
    expect(status).toHaveProperty('port')
  })
})
