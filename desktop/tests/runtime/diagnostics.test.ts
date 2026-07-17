import { describe, it, expect } from 'vitest'
import { PresenceDiagnostics } from '../../src/runtime/presence/diagnostics'
import { EmbodimentType, ConnectionState } from '../../src/runtime/types'

describe('PresenceDiagnostics', () => {
  it('computes frame rate from recorded frames', () => {
    const diag = new PresenceDiagnostics()
    diag.begin(1000)
    for (let i = 0; i < 10; i++) diag.recordFrame()
    const rate = diag.getFrameRate()
    expect(rate).toBeGreaterThanOrEqual(0)
  })

  it('exposes current embodiment and connection state', () => {
    const diag = new PresenceDiagnostics()
    diag.setEmbodiment('living-orb' as EmbodimentType, true)
    diag.setAnimationConnection('connected' as ConnectionState)
    expect(diag.getEmbodimentType()).toBe('living-orb')
    expect(diag.getAnimationConnection()).toBe('connected')
  })

  it('reports degraded health when no embodiment is attached', () => {
    const diag = new PresenceDiagnostics()
    const health = diag.getHealth()
    expect(health.status).toBe('degraded')
    expect(health.currentEmbodiment).toBe('none')
  })

  it('reports healthy status when embodiment and animation are connected', () => {
    const diag = new PresenceDiagnostics()
    diag.begin(0)
    diag.setEmbodiment('living-orb' as EmbodimentType, true)
    diag.setAnimationConnection('connected' as ConnectionState)
    diag.recordFrame()
    expect(diag.getHealth().status).toBe('healthy')
  })
})
