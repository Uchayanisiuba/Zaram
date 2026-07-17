import { IPresenceDiagnostics, IPresenceRuntime, IZaramKernel } from '../interfaces'

export class ZaramKernel implements IZaramKernel {
  private readonly presence: IPresenceRuntime
  private booted = false

  constructor(presence: IPresenceRuntime) {
    this.presence = presence
  }

  async boot(): Promise<void> {
    if (this.booted) return
    await this.presence.initialize()
    await this.presence.start()
    this.booted = true
  }

  async dispose(): Promise<void> {
    if (!this.booted) return
    await this.presence.shutdown()
    this.booted = false
  }

  getPresenceRuntime(): IPresenceRuntime {
    return this.presence
  }

  getDiagnostics(): IPresenceDiagnostics {
    return this.presence as unknown as IPresenceDiagnostics
  }
}
