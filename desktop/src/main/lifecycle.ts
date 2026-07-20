import { app, BrowserWindow, ipcMain } from 'electron'
import path from 'path'
import { WindowManager } from './window-manager'
import { BackendService } from '../services/backend-service'
import { getAppDataPath, getFrontendDistPath, isDevelopment } from '../config/paths'
import {
  bootstrapPresence,
  EmbodimentHost,
  IPresenceDiagnostics,
  IZaramKernel,
  IPresenceRuntime,
  IEmbodiment,
  Container
} from '../runtime'
import type { VSCodeCapabilityPack } from '../capabilities/vscode'

export class AppLifecycle {
  private windowManager: WindowManager
  private backendService: BackendService
  private isQuitting = false
  private presenceKernel: IZaramKernel | null = null
  private presenceEmbodiment: IEmbodiment | null = null
  private embodimentHost: EmbodimentHost | null = null
  private container: Container | null = null
  private vscodePack: VSCodeCapabilityPack | null = null

  constructor() {
    console.log('[STARTUP] AppLifecycle constructor')
    const appDataPath = getAppDataPath()
    this.windowManager = new WindowManager(appDataPath)
    console.log('[STARTUP] WindowManager created')
    this.backendService = new BackendService({
      autoStart: true
    })
    console.log('[STARTUP] BackendService created')
    this.bootstrapPresenceRuntime()
  }

  private bootstrapPresenceRuntime(): void {
    try {
      const backendStatus = this.backendService.getStatus()
      const backendUrl = backendStatus.running
        ? `http://${backendStatus.host}:${backendStatus.port}`
        : `http://127.0.0.1:8000`
      const result = bootstrapPresence({ backendUrl })
      this.container = result.container
      this.presenceKernel = result.buildKernel()
      this.presenceEmbodiment = result.embodiment
      this.vscodePack = this.container.resolve('VSCodePack') as VSCodeCapabilityPack | null
      this.wireRuntimeEventForwarding()
    } catch (error) {
      console.error('[STARTUP] Presence Runtime bootstrap failed:', error)
    }
  }

  private wireRuntimeEventForwarding(): void {
    const presence = this.presenceKernel?.getPresenceRuntime() as unknown as {
      getExecutiveSnapshot?: () => unknown
      subscribeExecutive?: (cb: (snapshot: unknown) => void) => () => void
    } | null

    if (!presence) return

    if (presence.subscribeExecutive) {
      presence.subscribeExecutive((snapshot: unknown) => {
        const win = this.windowManager.getMainWindow()
        if (win && !win.isDestroyed()) {
          win.webContents.send('runtime:executive-snapshot', snapshot)
        }
      })
    }

    if (this.container) {
      const exec = this.container.resolve('ExecutionRuntime') as { subscribe?: (cb: (event: unknown) => void) => () => void } | null
      if (exec?.subscribe) {
        exec.subscribe((event: unknown) => {
          const win = this.windowManager.getMainWindow()
          if (win && !win.isDestroyed()) {
            win.webContents.send('runtime:execution-event', event)
          }
        })
      }

      const workspace = this.container.resolve('WorkspaceRuntime') as { subscribe?: (cb: (event: unknown) => void) => () => void } | null
      if (workspace?.subscribe) {
        workspace.subscribe((event: unknown) => {
          const win = this.windowManager.getMainWindow()
          if (win && !win.isDestroyed()) {
            win.webContents.send('runtime:workspace-event', event)
          }
        })
      }
    }

    if (this.vscodePack) {
      this.vscodePack.subscribe((event) => {
        const win = this.windowManager.getMainWindow()
        if (win && !win.isDestroyed()) {
          win.webContents.send('vscode:event', event)
        }
      })
    }
  }

  async initialize(): Promise<void> {
    console.log('[STARTUP] Registering IPC handlers...')
    ipcMain.handle('app:quit', async () => {
      await this.shutdown()
      app.quit()
    })

    ipcMain.handle('backend:health', async () => {
      const healthy = await this.backendService.checkHealth()
      return healthy
    })

    ipcMain.handle('backend:status', () => {
      return this.backendService.getStatus()
    })

    ipcMain.handle('app:minimize', () => {
      this.windowManager.minimize()
    })

    ipcMain.handle('app:maximize', () => {
      this.windowManager.maximize()
    })

    ipcMain.handle('app:restore', () => {
      this.windowManager.restore()
    })

    ipcMain.handle('app:is-maximized', () => {
      return this.windowManager.isMaximized()
    })

    ipcMain.handle('presence:renderer-health', (_event, health: { rendererHealth?: string; gpuContextStatus?: string; fps?: number; droppedFrames?: number; gpuFrameTimeMs?: number }) => {
      const presence = this.presenceKernel?.getPresenceRuntime() as unknown as IPresenceDiagnostics | null
      if (!presence || !health) return
      if (health.rendererHealth) presence.setRendererHealth(health.rendererHealth as never)
      if (health.gpuContextStatus) presence.setGpuContextStatus(health.gpuContextStatus as never)
      if (typeof health.fps === 'number') presence.setRefreshRate(health.fps)
      if (typeof health.droppedFrames === 'number') {
        const current = presence.getDroppedFrames()
        if (health.droppedFrames > current) {
          presence.recordDroppedFrame()
        }
      }
      if (typeof health.gpuFrameTimeMs === 'number') presence.setGpuFrameTime(health.gpuFrameTimeMs)
      const embodiment = this.presenceEmbodiment as unknown as { applyRendererHealth?: (h: boolean, m?: string) => void }
      if (embodiment?.applyRendererHealth) {
        embodiment.applyRendererHealth(health.rendererHealth !== 'unhealthy', health.rendererHealth)
      }
    })

    ipcMain.handle('presence:diagnostics', () => {
      const presence = this.presenceKernel?.getPresenceRuntime() as unknown as IPresenceDiagnostics | null
      if (!presence) return null
      return presence.getHealth()
    })

    ipcMain.handle('runtime:get-presence-health', () => {
      const presence = this.presenceKernel?.getPresenceRuntime() as unknown as IPresenceDiagnostics | null
      if (!presence) return null
      return presence.getHealth()
    })

    ipcMain.handle('runtime:get-presence-status', () => {
      const presence = this.presenceKernel?.getPresenceRuntime() as unknown as IPresenceRuntime | null
      if (!presence || !this.presenceKernel) return null
      const diagnostics = this.presenceKernel.getDiagnostics()
      return {
        status: presence.getStatus(),
        health: presence.getHealth(),
        frameRate: diagnostics.getFrameRate(),
        animationConnection: diagnostics.getAnimationConnection()
      }
    })

    ipcMain.handle('runtime:start', async () => {
      const presence = this.presenceKernel?.getPresenceRuntime() as unknown as IPresenceRuntime | null
      if (!presence) return { success: false }
      await presence.start()
      return { success: true }
    })

    ipcMain.handle('runtime:pause', async () => {
      const presence = this.presenceKernel?.getPresenceRuntime() as unknown as IPresenceRuntime | null
      if (!presence) return { success: false }
      await presence.pause()
      return { success: true }
    })

    ipcMain.handle('runtime:resume', async () => {
      const presence = this.presenceKernel?.getPresenceRuntime() as unknown as IPresenceRuntime | null
      if (!presence) return { success: false }
      await presence.resume()
      return { success: true }
    })

    ipcMain.handle('runtime:get-executive-snapshot', () => {
      const presence = this.presenceKernel?.getPresenceRuntime() as unknown as { getExecutiveSnapshot?: () => unknown } | null
      if (!presence?.getExecutiveSnapshot) return null
      return presence.getExecutiveSnapshot()
    })

    ipcMain.handle('executive:plan', (_event, query: string) => {
      if (!this.container) return null
      const exec = this.container.resolve('ExecutiveRuntime') as { plan?: (query: string) => unknown } | null
      return exec?.plan?.(query) ?? null
    })

    ipcMain.handle('executive:get-plan', () => {
      if (!this.container) return null
      const exec = this.container.resolve('ExecutiveRuntime') as { getCurrentPlan?: () => unknown } | null
      return exec?.getCurrentPlan?.() ?? null
    })

    ipcMain.handle('executive:get-confidence', () => {
      if (!this.container) return 0
      const exec = this.container.resolve('ExecutiveRuntime') as { getConfidence?: () => number } | null
      return exec?.getConfidence?.() ?? 0
    })

    ipcMain.handle('executive:get-evidence', () => {
      if (!this.container) return []
      const exec = this.container.resolve('ExecutiveRuntime') as { getEvidence?: () => string[] } | null
      return exec?.getEvidence?.() ?? []
    })

    ipcMain.handle('executive:get-metrics', () => {
      if (!this.container) return []
      const exec = this.container.resolve('ExecutiveRuntime') as { getCapabilityMetrics?: () => unknown[] } | null
      return exec?.getCapabilityMetrics?.() ?? []
    })

    ipcMain.handle('runtime:get-capability-snapshot', () => {
      if (!this.container) return null
      const cap = this.container.resolve('CapabilityRuntime') as { getSnapshot?: () => unknown } | null
      return cap?.getSnapshot?.() ?? null
    })

    ipcMain.handle('runtime:get-capability-by-id', (_event, id: string) => {
      if (!this.container) return null
      const cap = this.container.resolve('CapabilityRuntime') as { get?: (id: string) => unknown } | null
      return cap?.get?.(id) ?? null
    })

    ipcMain.handle('runtime:get-capability-by-category', (_event, category: string) => {
      if (!this.container) return []
      const cap = this.container.resolve('CapabilityRuntime') as { getByCategory?: (cat: string) => unknown[] } | null
      return cap?.getByCategory?.(category) ?? []
    })

    ipcMain.handle('runtime:get-execution-history', () => {
      if (!this.container) return []
      const exec = this.container.resolve('ExecutionRuntime') as { getHistory?: () => unknown[] } | null
      return exec?.getHistory?.() ?? []
    })

    ipcMain.handle('runtime:get-execution', (_event, id: string) => {
      if (!this.container) return null
      const exec = this.container.resolve('ExecutionRuntime') as { getExecution?: (id: string) => unknown } | null
      return exec?.getExecution?.(id) ?? null
    })

    ipcMain.handle('runtime:execute-capability', async (_event, capabilityId: string, input: unknown, options?: unknown) => {
      if (!this.container) return { success: false, error: 'No execution runtime' }
      const exec = this.container.resolve('ExecutionRuntime') as { execute: (req: unknown) => string } | null
      if (!exec) return { success: false, error: 'No execution runtime' }
      try {
        const id = exec.execute({
          capabilityId,
          input,
          context: {
            correlationId: `ui-${Date.now()}`,
            grantedPermissions: [],
            actor: 'ui',
            createdAt: Date.now()
          },
          options: options as any
        })
        return { success: true, id }
      } catch (error) {
        return { success: false, error: String(error) }
      }
    })

    ipcMain.handle('runtime:cancel-execution', (_event, id: string) => {
      if (!this.container) return false
      const exec = this.container.resolve('ExecutionRuntime') as { cancel: (id: string) => boolean } | null
      return exec?.cancel?.(id) ?? false
    })

    ipcMain.handle('runtime:retry-execution', (_event, id: string) => {
      if (!this.container) return false
      const exec = this.container.resolve('ExecutionRuntime') as { retry: (id: string) => boolean } | null
      return exec?.retry?.(id) ?? false
    })

    ipcMain.handle('runtime:get-world-state', () => {
      const presence = this.presenceKernel?.getPresenceRuntime() as unknown as { getWorldState?: () => unknown } | null
      if (!presence?.getWorldState) return null
      return presence.getWorldState()
    })

    ipcMain.handle('runtime:get-cognitive-state', () => {
      const presence = this.presenceKernel?.getPresenceRuntime() as unknown as { getCognitiveState?: () => unknown } | null
      if (!presence?.getCognitiveState) return null
      return presence.getCognitiveState()
    })

    ipcMain.handle('runtime:get-attention-state', () => {
      const presence = this.presenceKernel?.getPresenceRuntime() as unknown as { getAttentionState?: () => unknown } | null
      if (!presence?.getAttentionState) return null
      return presence.getAttentionState()
    })

    ipcMain.handle('runtime:get-relationship-state', () => {
      const presence = this.presenceKernel?.getPresenceRuntime() as unknown as { getRelationshipState?: () => unknown } | null
      if (!presence?.getRelationshipState) return null
      return presence.getRelationshipState()
    })

    ipcMain.handle('runtime:get-character-frame', () => {
      const presence = this.presenceKernel?.getPresenceRuntime() as unknown as { getCharacterFrame?: () => unknown } | null
      if (!presence?.getCharacterFrame) return null
      return presence.getCharacterFrame()
    })

    ipcMain.handle('runtime:get-workspace-state', () => {
      const presence = this.presenceKernel?.getPresenceRuntime() as unknown as { getWorkspaceState?: () => unknown } | null
      if (!presence?.getWorkspaceState) return null
      return presence.getWorkspaceState()
    })

    ipcMain.handle('runtime:get-workspace-context', () => {
      const presence = this.presenceKernel?.getPresenceRuntime() as unknown as { getWorkspaceContext?: () => unknown } | null
      if (!presence?.getWorkspaceContext) return null
      return presence.getWorkspaceContext()
    })

    ipcMain.handle('runtime:get-workspace-snapshot', () => {
      const presence = this.presenceKernel?.getPresenceRuntime() as unknown as { getWorkspaceSnapshot?: () => unknown } | null
      if (!presence?.getWorkspaceSnapshot) return null
      return presence.getWorkspaceSnapshot()
    })

    ipcMain.handle('runtime:get-workspace-project', (_event, path: string) => {
      const presence = this.presenceKernel?.getPresenceRuntime() as unknown as { getWorkspaceState?: () => { projects: any[] } } | null
      if (!presence?.getWorkspaceState) return null
      const state = presence.getWorkspaceState()
      const project = state.projects.find((p: any) => p.rootPath === path || p.relativePath === path)
      return project ? { ...project } : null
    })

    ipcMain.handle('runtime:get-workspace-all-projects', () => {
      const presence = this.presenceKernel?.getPresenceRuntime() as unknown as { getWorkspaceState?: () => { projects: any[] } } | null
      if (!presence?.getWorkspaceState) return []
      const state = presence.getWorkspaceState()
      return state.projects.map((p: any) => ({ ...p }))
    })

    ipcMain.handle('vscode:get-snapshot', () => {
      if (!this.vscodePack) return null
      return this.vscodePack.getAdapter().getSnapshot()
    })

    ipcMain.handle('vscode:get-editor', () => {
      if (!this.vscodePack) return null
      return this.vscodePack.getAdapter().getEditorInfo()
    })

    ipcMain.handle('vscode:get-workspace-folders', () => {
      if (!this.vscodePack) return []
      return this.vscodePack.getAdapter().getWorkspaceFolders()
    })

    ipcMain.handle('vscode:get-diagnostics', () => {
      if (!this.vscodePack) return []
      return this.vscodePack.getAdapter().getDiagnostics()
    })

    ipcMain.handle('vscode:get-git-status', () => {
      if (!this.vscodePack) return null
      return this.vscodePack.getAdapter().getGitStatus()
    })

    ipcMain.handle('filesystem:get-metrics', () => {
      if (!this.container) return null
      try {
        const fs = this.container.resolve('FilesystemPack') as { getMetrics?: () => unknown } | null
        return fs?.getMetrics?.() ?? null
      } catch {
        return null
      }
    })

    ipcMain.handle('runtime:workspace-discover', async (_event, signals: unknown, mode: 'shallow' | 'deep') => {
      const container = this.presenceKernel as unknown as { getContainer?: () => { resolve: (token: string) => { discover: (signals: unknown, mode: string) => Promise<void> } } } | null
      if (!container?.getContainer) return { success: false, error: 'No workspace runtime' }
      try {
        const workspace = container.getContainer().resolve('workspaceRuntime')
        await workspace.discover(signals as any, mode)
        return { success: true }
      } catch (error) {
        return { success: false, error: String(error) }
      }
    })

    ipcMain.handle('runtime:workspace-set-root', async (_event, rootPath: string) => {
      const container = this.presenceKernel as unknown as { getContainer?: () => { resolve: (token: string) => { setRootPath: (path: string) => void } } } | null
      if (!container?.getContainer) return { success: false, error: 'No workspace runtime' }
      try {
        const workspace = container.getContainer().resolve('workspaceRuntime')
        workspace.setRootPath(rootPath)
        return { success: true }
      } catch (error) {
        return { success: false, error: String(error) }
      }
    })

    await this.start()
  }

  async start(): Promise<void> {
    console.log('[STARTUP] Creating splash window...')
    this.windowManager.createSplashWindow()

    try {
      console.log('[STARTUP] Starting backend service...')
      const backendStatus = await this.backendService.start()
      
      if (!backendStatus.running) {
        console.error('[STARTUP] Failed to start backend:', backendStatus.error)
      } else {
        console.log('[STARTUP] Backend service started')
      }
    } catch (error) {
      console.error('[STARTUP] Backend startup error:', error)
    }

    console.log('[STARTUP] Showing main window...')
    await this.showMainWindow()
    this.windowManager.closeSplash()

    this.autoDetectWorkspace()

    console.log('[STARTUP] Startup complete')
  }

  private autoDetectWorkspace(): void {
    try {
      const projectRoot = path.join(__dirname, '..', '..', '..', '..')
      const container = this.presenceKernel as unknown as { getContainer?: () => { resolve: (token: string) => { setRootPath: (path: string) => void; discover: (signals: unknown, mode: string) => Promise<void> } } } | null
      if (!container?.getContainer) return
      const workspace = container.getContainer().resolve('workspaceRuntime')
      workspace.setRootPath(projectRoot)
      workspace.discover([{ path: projectRoot, type: 'root' }], 'shallow').catch((error) => {
        console.error('[STARTUP] Workspace auto-detection failed:', error)
      })
    } catch (error) {
      console.error('[STARTUP] Workspace auto-detection error:', error)
    }
  }

  private async showMainWindow(): Promise<void> {
    const mainWindow = this.windowManager.createMainWindow()

    const frontendPath = getFrontendDistPath()
    const devServerUrl = 'http://localhost:5173'

    mainWindow.webContents.on('console-message', (_event, level, message) => {
      console.log(`[Renderer:${level}] ${message}`)
    })

    mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription) => {
      console.error('[Renderer] did-fail-load:', errorCode, errorDescription)
    })

    mainWindow.webContents.on('render-process-gone', (_event, details) => {
      console.error('[Renderer] render-process-gone:', details)
    })

    mainWindow.webContents.on('crashed', () => {
      console.error('[Renderer] crashed')
    })

    const showWindow = () => {
      if (!mainWindow.isDestroyed()) {
        mainWindow.show()
      }
    }

    mainWindow.once('ready-to-show', showWindow)

    if (isDevelopment()) {
      await mainWindow.loadURL(devServerUrl)
      mainWindow.webContents.openDevTools({ mode: 'detach' })
    } else {
      const indexPath = path.join(frontendPath, 'index.html')
      await mainWindow.loadFile(indexPath)
    }

    this.attachEmbodimentWindow(mainWindow)

    if (mainWindow.isDestroyed()) return
    if (!mainWindow.isVisible()) {
      mainWindow.show()
    }
  }

  private attachEmbodimentWindow(mainWindow: BrowserWindow): void {
    if (!this.presenceKernel) return
    const presence = this.presenceKernel.getPresenceRuntime()
    this.embodimentHost = new EmbodimentHost({
      getWindow: () => this.windowManager.getMainWindow(),
      presence,
      throttleOnHidden: true
    })
    this.embodimentHost.mount()
    if (this.presenceEmbodiment) {
      this.embodimentHost.attachToEmbodiment(this.presenceEmbodiment)
    }
    void this.embodimentHost.boot().catch((error) => {
      console.error('Presence Runtime boot failed:', error)
    })
  }

  private setAnimationRuntimeStatus(status: 'stopped' | 'running' | 'paused'): void {
    const presence = this.presenceKernel?.getPresenceRuntime() as unknown as IPresenceDiagnostics | null
    presence?.setAnimationRuntimeStatus(status)
  }

  async shutdown(): Promise<void> {
    this.vscodePack?.getAdapter().stop()
    await this.disposePresenceRuntime()
    this.cleanup()
    await this.backendService.stop()
  }

  private async disposePresenceRuntime(): Promise<void> {
    this.embodimentHost?.unmount()
    if (this.presenceKernel) {
      try {
        await this.presenceKernel.dispose()
      } catch (error) {
        console.error('Presence Runtime shutdown failed:', error)
      }
    }
  }

  private cleanup(): void {
    this.windowManager.destroy()
  }

  getWindowManager(): WindowManager {
    return this.windowManager
  }

  getBackendService(): BackendService {
    return this.backendService
  }

  getPresenceKernel(): IZaramKernel | null {
    return this.presenceKernel
  }

  getPresenceRuntime(): IPresenceRuntime | null {
    return this.presenceKernel ? this.presenceKernel.getPresenceRuntime() : null
  }
}
