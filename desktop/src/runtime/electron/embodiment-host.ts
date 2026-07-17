import { screen } from 'electron'
import { IEmbodiment, IPresenceRuntime, IRenderTransport } from '../interfaces'
import { WebContentsTransport } from './render-transport'

export interface ViewportInfo {
  width: number
  height: number
  scaleFactor: number
}

export interface EmbodimentHostOptions {
  getWindow: () => unknown
  presence: IPresenceRuntime
  channel?: string
  viewportChannel?: string
  throttleOnHidden?: boolean
}

type AnyEventEmitter = {
  on?: (event: string, listener: (...args: unknown[]) => void) => void
  off?: (event: string, listener: (...args: unknown[]) => void) => void
  once?: (event: string, listener: (...args: unknown[]) => void) => void
}

export class EmbodimentHost {
  private readonly options: EmbodimentHostOptions
  private readonly transport: WebContentsTransport
  private readonly detachHandlers: Array<() => void> = []
  private readonly viewportListeners: Array<(info: ViewportInfo) => void> = []
  private attached = false
  private recovering = false

  constructor(options: EmbodimentHostOptions) {
    this.options = options
    this.transport = new WebContentsTransport(options.getWindow, options.channel ?? 'presence:frame')
  }

  getTransport(): IRenderTransport {
    return this.transport
  }

  onViewport(listener: (info: ViewportInfo) => void): () => void {
    this.viewportListeners.push(listener)
    return () => {
      const index = this.viewportListeners.indexOf(listener)
      if (index >= 0) this.viewportListeners.splice(index, 1)
    }
  }

  mount(): void {
    if (this.attached) return
    const window = this.options.getWindow() as (AnyEventEmitter & {
      webContents?: AnyEventEmitter
      isDestroyed?: () => boolean
      getSize?: () => [number, number]
    }) | null | undefined
    if (!window) return
    this.attached = true

    this.safeOn(window, 'resize', () => this.publishViewport())
    this.safeOn(window, 'show', () => this.onVisible())
    this.safeOn(window, 'hide', () => this.onHidden())
    this.safeOn(window, 'closed', () => this.unmount())

    const webContents = window.webContents
    this.safeOn(webContents, 'crashed', () => this.recoverContext())
    this.safeOn(webContents, 'did-fail-load', () => this.recoverContext())

    this.safeOn(screen as unknown as AnyEventEmitter, 'display-metrics-changed', () =>
      this.publishViewport()
    )

    this.publishViewport()
  }

  unmount(): void {
    this.detachHandlers.forEach((off) => {
      try {
        off()
      } catch {
        /* ignore teardown errors */
      }
    })
    this.detachHandlers.length = 0
    this.attached = false
  }

  attachToEmbodiment(embodiment: IEmbodiment): void {
    const aware = embodiment as unknown as { setTransport?: (t: IRenderTransport) => void }
    if (typeof aware.setTransport === 'function') {
      aware.setTransport(this.transport)
    }
  }

  async boot(): Promise<void> {
    await this.options.presence.initialize()
    await this.options.presence.start()
  }

  private onVisible(): void {
    if (this.options.throttleOnHidden !== false) {
      void this.options.presence.resume()
    }
  }

  private onHidden(): void {
    if (this.options.throttleOnHidden !== false) {
      void this.options.presence.pause()
    }
  }

  private async recoverContext(): Promise<void> {
    if (this.recovering) return
    this.recovering = true
    try {
      await this.options.presence.shutdown()
      await this.options.presence.initialize()
      await this.options.presence.start()
    } catch {
      /* recovery best-effort */
    } finally {
      this.recovering = false
    }
  }

  private publishViewport(): void {
    const window = this.options.getWindow() as
      | { isDestroyed?: () => boolean; getSize?: () => [number, number]; webContents?: { send?: (c: string, d: unknown) => void } }
      | null
      | undefined
    if (!window || (window.isDestroyed && window.isDestroyed())) return
    const [width, height] = window.getSize ? window.getSize() : [0, 0]
    const scaleFactor = screen && screen.getPrimaryDisplay ? screen.getPrimaryDisplay().scaleFactor : 1
    const info: ViewportInfo = { width, height, scaleFactor }
    this.viewportListeners.forEach((listener) => listener(info))
    const send = window.webContents?.send
    if (typeof send === 'function') {
      try {
        send.call(window.webContents, this.options.viewportChannel ?? 'presence:viewport', info)
      } catch {
        /* renderer may be torn down */
      }
    }
  }

  private safeOn(target: AnyEventEmitter | null | undefined, event: string, handler: () => void): void {
    if (target && typeof target.on === 'function') {
      target.on(event, handler as (...args: unknown[]) => void)
      this.detachHandlers.push(() => {
        if (typeof target.off === 'function') {
          target.off(event, handler as (...args: unknown[]) => void)
        }
      })
    }
  }
}
