type AnyApi = Record<string, any>

const zaram = (typeof window !== 'undefined' && (window as AnyApi).zaram) ? (window as AnyApi).zaram : null
const electron = (typeof window !== 'undefined' && (window as AnyApi).electron) ? (window as AnyApi).electron : null

export const isDesktop = Boolean(zaram) || Boolean(electron)

function safe<T extends any[], R>(
  fn: (api: AnyApi, ...args: T) => R,
  fallback?: R
): (...args: T) => R {
  return (...args: T) => {
    try {
      if (zaram) return fn(zaram, ...args)
      if (electron) return fn(electron, ...args)
      return (fallback ?? (null as any)) as R
    } catch {
      return (fallback ?? (null as any)) as R
    }
  }
}

function safeSync<T extends any[], R>(
  fn: (api: AnyApi, ...args: T) => R,
  fallback: R
): (...args: T) => R {
  return (...args: T) => {
    try {
      if (zaram) return fn(zaram, ...args)
      if (electron) return fn(electron, ...args)
      return fallback
    } catch {
      return fallback
    }
  }
}

export const desktop = {
  app: {
    getInfo: safe((api) => api.app.getInfo?.()),
    getVersion: safe((api) => api.app.getVersion?.()),
    getPlatform: safe((api) => api.app.getPlatform?.()),
  },
  backend: {
    getStatus: safe((api) => api.backend.getStatus?.()),
    checkHealth: safe((api) => api.backend.checkHealth?.()),
    onStatus: (cb: (status: any) => void) => {
      if (zaram && zaram.backend && zaram.backend.onStatus) return zaram.backend.onStatus(cb)
      return () => {}
    },
  },
  presence: {
    getHealth: safe((api) => api.runtime?.getPresenceHealth?.()),
    getStatus: safe((api) => api.runtime?.getPresenceStatus?.()),
    getDiagnostics: safe((api) => api.presence?.getDiagnostics?.()),
    onFrame: (cb: (frame: any) => void) => {
      if (zaram && zaram.presence && zaram.presence.onFrame) return zaram.presence.onFrame(cb)
      if (electron && electron.receive) {
        electron.receive('presence:frame', cb)
        return () => electron.receive('presence:frame', cb)
      }
      return () => {}
    },
    onViewport: (cb: (vp: any) => void) => {
      if (zaram && zaram.presence && zaram.presence.onViewport) return zaram.presence.onViewport(cb)
      if (electron && electron.receive) {
        electron.receive('presence:viewport', cb)
        return () => electron.receive('presence:viewport', cb)
      }
      return () => {}
    },
  },
  executive: {
    getSnapshot: safe((api) => api.runtime?.getExecutiveSnapshot?.()),
    plan: safe((api, query: string) => api.executive?.plan?.(query)),
    getPlan: safe((api) => api.executive?.getPlan?.()),
    getConfidence: safe((api) => api.executive?.getConfidence?.()),
    getEvidence: safe((api) => api.executive?.getEvidence?.()),
    getMetrics: safe((api) => api.executive?.getMetrics?.()),
    onSnapshot: (cb: (snapshot: any) => void) => {
      if (zaram && zaram.runtime && zaram.runtime.onExecutiveSnapshot) return zaram.runtime.onExecutiveSnapshot(cb)
      return () => {}
    },
  },
  capability: {
    getSnapshot: safe((api) => api.runtime?.getCapabilitySnapshot?.()),
    getById: safe((api, id: string) => api.runtime?.getCapabilityById?.(id)),
    getByCategory: safe((api, cat: string) => api.runtime?.getCapabilityByCategory?.(cat)),
  },
  execution: {
    getHistory: safe((api) => api.runtime?.getExecutionHistory?.()),
    getExecution: safe((api, id: string) => api.runtime?.getExecution?.(id)),
    execute: safe((api, capabilityId: string, input: any, options?: any) => api.runtime?.executeCapability?.(capabilityId, input, options)),
    cancel: safe((api, id: string) => api.runtime?.cancelExecution?.(id)),
    retry: safe((api, id: string) => api.runtime?.retryExecution?.(id)),
    onEvent: (cb: (event: any) => void) => {
      if (zaram && zaram.runtime && zaram.runtime.onExecutionEvent) return zaram.runtime.onExecutionEvent(cb)
      return () => {}
    },
    onHistoryChange: (cb: () => void) => {
      const handler = () => cb()
      if (zaram && zaram.runtime) {
        zaram.runtime.onExecutionEvent(handler)
        return () => { if (zaram.runtime?.onExecutionEvent) zaram.runtime.onExecutionEvent(handler) }
      }
      return () => {}
    },
  },
  world: {
    getState: safe((api) => api.runtime?.getWorldState?.()),
  },
  cognitive: {
    getState: safe((api) => api.runtime?.getCognitiveState?.()),
    getAttention: safe((api) => api.runtime?.getAttentionState?.()),
    getRelationship: safe((api) => api.runtime?.getRelationshipState?.()),
  },
  character: {
    getFrame: safe((api) => api.runtime?.getCharacterFrame?.()),
  },
  workspace: {
    getState: safe((api) => api.workspace?.getState?.()),
    getContext: safe((api) => api.workspace?.getContext?.()),
    getSnapshot: safe((api) => api.workspace?.getSnapshot?.()),
    provideContext: safe((api) => api.workspace?.getSnapshot?.()),
    getProject: safe((api, path: string) => api.workspace?.getProject?.(path)),
    getAllProjects: safe((api) => api.workspace?.getAllProjects?.()),
    discover: safe((api, signals: unknown, mode: 'shallow' | 'deep') => api.workspace?.discover?.(signals, mode)),
    onEvent: (cb: (event: any) => void) => {
      if (zaram && zaram.workspace && zaram.workspace.subscribe) return zaram.workspace.subscribe(cb)
      return () => {}
    },
  },
  dialog: {
    showOpen: safe((api) => api.dialog?.showOpen?.()),
    showSave: safe((api) => api.dialog?.showSave?.()),
    showMessage: safe((api) => api.dialog?.showMessage?.()),
  },
  notify: {
    show: safe((api) => api.notify?.show?.()),
  },
  shell: {
    openExternal: safe((api, url: string) => api.shell?.openExternal?.(url)),
    openPath: safe((api, p: string) => api.shell?.openPath?.(p)),
    showItemInFolder: safe((api, p: string) => api.shell?.showItemInFolder?.(p)),
  },
  clipboard: {
    readText: safe((api) => api.clipboard?.readText?.()),
    writeText: safe((api, text: string) => api.clipboard?.writeText?.(text)),
  },
  system: {
    getPlatform: safe((api) => api.system?.getPlatform?.()),
    getVersion: safe((api) => api.system?.getVersion?.()),
    getArch: safe((api) => api.system?.getArch?.()),
  },
  settings: {
    get: safe((api, key: string) => api.settings?.get?.(key)),
    set: safe((api, key: string, value: any) => api.settings?.set?.(key, value)),
    getAll: safe((api) => api.settings?.getAll?.(), {}),
  },
  filesystem: {
    getMetrics: safe((api) => api.filesystem?.getMetrics?.()),
  },
  vscode: {
    getSnapshot: safe((api) => api.vscode?.getSnapshot?.()),
    getEditor: safe((api) => api.vscode?.getEditor?.()),
    getWorkspaceFolders: safe((api) => api.vscode?.getWorkspaceFolders?.()),
    getDiagnostics: safe((api) => api.vscode?.getDiagnostics?.()),
    getGitStatus: safe((api) => api.vscode?.getGitStatus?.()),
    onEvent: (cb: (event: any) => void) => {
      if (zaram && zaram.vscode && zaram.vscode.onEvent) return zaram.vscode.onEvent(cb)
      return () => {}
    },
  }
}

export default desktop
