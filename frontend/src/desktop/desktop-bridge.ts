type AnyApi = Record<string, any>

const zaram = (typeof window !== 'undefined' && (window as AnyApi).zaram) ? (window as AnyApi).zaram : null

export const isDesktop = Boolean(zaram)

function safe<T extends any[], R>(
  fn: (api: AnyApi, ...args: T) => R,
  fallback?: R
): (...args: T) => R {
  return (...args: T) => {
    try {
      if (zaram) return fn(zaram, ...args)
      return (fallback ?? (null as any)) as R
    } catch {
      return (fallback ?? (null as any)) as R
    }
  }
}

export const desktop = {
  app: {
    getInfo: safe((api) => api.app?.getInfo?.()),
    getVersion: safe((api) => api.app?.getVersion?.()),
    getPlatform: safe((api) => api.app?.getPlatform?.()),
  },
  backend: {
    getStatus: safe((api) => api.backend?.getStatus?.()),
    checkHealth: safe((api) => api.backend?.getStatus?.().then((s: any) => s.state === 'available')),
    onStatus: (cb: (status: any) => void) => {
      if (zaram?.backend?.onStatus) return zaram.backend.onStatus(cb)
      return () => {}
    },
  },
  presence: {
    getHealth: safe((api) => api.presence?.getHealth?.()),
    getStatus: safe((api) => api.presence?.getStatus?.()),
    getDiagnostics: safe((api) => api.presence?.getDiagnostics?.()),
    onFrame: (cb: (frame: any) => void) => {
      if (zaram?.presence?.onFrame) return zaram.presence.onFrame(cb)
      return () => {}
    },
    onViewport: (cb: (vp: any) => void) => {
      if (zaram?.presence?.onViewport) return zaram.presence.onViewport(cb)
      return () => {}
    },
  },
  executive: {
    getSnapshot: safe((api) => api.executive?.getSnapshot?.()),
    plan: safe((api, query: string, options?: { persona?: string; model?: string }) => { console.log('[Bridge] executive.plan:', query, options); return api.executive?.plan?.(query, options) }),
    getPlan: safe((api) => api.executive?.getPlan?.()),
    getConfidence: safe((api) => api.executive?.getConfidence?.()),
    getEvidence: safe((api) => api.executive?.getEvidence?.()),
    getMetrics: safe((api) => api.executive?.getMetrics?.()),
    onSnapshot: (cb: (snapshot: any) => void) => {
      if (zaram?.executive?.subscribe) return zaram.executive.subscribe(cb)
      return () => {}
    },
  },
  capability: {
    getSnapshot: safe((api) => api.capability?.getSnapshot?.()),
    getById: safe((api, id: string) => { console.log('[Bridge] capability.getById:', id); return api.capability?.getById?.(id) }),
    getByCategory: safe((api, cat: string) => { console.log('[Bridge] capability.getByCategory:', cat); return api.capability?.getByCategory?.(cat) }),
  },
  execution: {
    getHistory: safe((api) => { console.log('[Bridge] execution.getHistory'); return api.execution?.getHistory?.() }),
    getExecution: safe((api, id: string) => { console.log('[Bridge] execution.getExecution:', id); return api.execution?.getExecution?.(id) }),
    execute: safe((api, capabilityId: string, input: any, options?: any) => { console.log('[Bridge] execution.execute:', capabilityId, input); return api.execution?.execute?.(capabilityId, input, options) }),
    cancel: safe((api, id: string) => { console.log('[Bridge] execution.cancel:', id); return api.execution?.cancel?.(id) }),
    retry: safe((api, id: string) => { console.log('[Bridge] execution.retry:', id); return api.execution?.retry?.(id) }),
    onEvent: (cb: (event: any) => void) => {
      console.log('[Bridge] execution.onEvent subscribed')
      if (zaram?.execution?.subscribe) return zaram.execution.subscribe(cb)
      return () => {}
    },
  },
  world: {
    getState: safe((api) => api.world?.getState?.()),
  },
  cognitive: {
    getState: safe((api) => api.cognitive?.getState?.()),
    getAttention: safe((api) => api.cognitive?.getAttention?.()),
    getRelationship: safe((api) => api.cognitive?.getRelationship?.()),
  },
  character: {
    getFrame: safe((api) => api.character?.getFrame?.()),
  },
  workspace: {
    getState: safe((api) => api.workspace?.getState?.()),
    getContext: safe((api) => api.workspace?.getContext?.()),
    getSnapshot: safe((api) => api.workspace?.getSnapshot?.()),
    setRootPath: safe((api, path: string) => api.workspace?.setRootPath?.(path)),
    provideContext: safe((api) => api.workspace?.getSnapshot?.()),
    getProject: safe((api, path: string) => api.workspace?.getProject?.(path)),
    getAllProjects: safe((api) => api.workspace?.getAllProjects?.()),
    discover: safe((api, signals: unknown, mode: 'shallow' | 'deep') => api.workspace?.discover?.(signals, mode)),
    onEvent: (cb: (event: any) => void) => {
      if (zaram?.workspace?.subscribe) return zaram.workspace.subscribe(cb)
      return () => {}
    },
  },
  dialog: {
    showOpen: safe((api, opts?: any) => api.dialog?.openFile?.(opts)),
    showSave: safe((api, opts?: any) => api.dialog?.saveFile?.(opts)),
    showMessage: safe((api, title?: string, body?: string) => api.notification?.show?.(title, body)),
    selectDirectory: safe((api, opts?: any) => api.dialog?.selectDirectory?.(opts)),
  },
  notify: {
    show: safe((api, opts?: any) => api.notify?.show?.(opts)),
  },
  shell: {
    openExternal: safe((api, url: string) => api.shell?.openExternal?.(url)),
    openPath: safe((api, p: string) => api.shell?.openPath?.(p)),
    showItemInFolder: safe((api, p: string) => api.shell?.openPath?.(p)),
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
      if (zaram?.vscode?.onEvent) return zaram.vscode.onEvent(cb)
      return () => {}
    },
  },
  runtime: {
    desktopGetSources: safe((api, opts?: any) => api.runtime?.desktopGetSources?.(opts)),
  }
}

export default desktop
