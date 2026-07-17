import { FrameState } from '../types'
import { IRenderTransport } from '../interfaces'

export class NullRenderTransport implements IRenderTransport {
  private lastFrameState: FrameState | null = null
  private readonly readyListeners: Array<() => void> = []
  private ready = true

  sendFrameState(frameState: FrameState): void {
    this.lastFrameState = frameState
  }

  isReady(): boolean {
    return this.ready
  }

  onReady(listener: () => void): void {
    if (this.ready) {
      listener()
      return
    }
    this.readyListeners.push(listener)
  }

  getLastFrameState(): FrameState | null {
    return this.lastFrameState
  }

  setReady(value: boolean): void {
    this.ready = value
    if (value) {
      const pending = this.readyListeners.splice(0)
      pending.forEach((listener) => listener())
    }
  }
}

export class WebContentsTransport implements IRenderTransport {
  private readonly getWindow: () => unknown
  private readonly channel: string

  constructor(getWindow: () => unknown, channel = 'presence:frame') {
    this.getWindow = getWindow
    this.channel = channel
  }

  sendFrameState(frameState: FrameState): void {
    const window = this.getWindow() as
      | { isDestroyed?: () => boolean; webContents?: { send?: (channel: string, data: unknown) => void } }
      | null
      | undefined
    if (!window || (window.isDestroyed && window.isDestroyed())) return
    const send = window?.webContents?.send
    if (typeof send === 'function') {
      try {
        send.call(window.webContents, this.channel, frameState)
      } catch {
        /* renderer may be navigating or torn down; drop frame */
      }
    }
  }

  isReady(): boolean {
    const window = this.getWindow() as { isDestroyed?: () => boolean } | null | undefined
    return Boolean(window) && !(window?.isDestroyed?.() ?? true)
  }

  onReady(listener: () => void): void {
    const window = this.getWindow() as
      | { once?: (event: string, listener: () => void) => void; isDestroyed?: () => boolean }
      | null
      | undefined
    if (this.isReady()) {
      listener()
      return
    }
    if (window && typeof window.once === 'function') {
      const handler = (): void => {
        if (this.isReady()) listener()
      }
      window.once('ready-to-show', handler)
      window.once('show', handler)
    }
  }
}
