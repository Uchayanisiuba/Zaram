import { contextBridge, ipcRenderer } from 'electron'

const runtimeAPI = {
  presence: {
    getHealth: () => ipcRenderer.invoke('runtime:get-presence-health'),
    getStatus: () => ipcRenderer.invoke('runtime:get-presence-status'),
    start: () => ipcRenderer.invoke('runtime:start'),
    pause: () => ipcRenderer.invoke('runtime:pause'),
    resume: () => ipcRenderer.invoke('runtime:resume'),
    onFrame: (cb: (frame: unknown) => void) => {
      const wrapped = (_event: unknown, frame: unknown) => cb(frame)
      ipcRenderer.on('presence:frame', wrapped)
      return () => ipcRenderer.removeListener('presence:frame', wrapped)
    },
    onViewport: (cb: (vp: unknown) => void) => {
      const wrapped = (_event: unknown, vp: unknown) => cb(vp)
      ipcRenderer.on('presence:viewport', wrapped)
      return () => ipcRenderer.removeListener('presence:viewport', wrapped)
    }
  },
  executive: {
    getSnapshot: () => ipcRenderer.invoke('runtime:get-executive-snapshot'),
    plan: (query: string) => ipcRenderer.invoke('executive:plan', query),
    getPlan: () => ipcRenderer.invoke('executive:get-plan'),
    getConfidence: () => ipcRenderer.invoke('executive:get-confidence'),
    getEvidence: () => ipcRenderer.invoke('executive:get-evidence'),
    getMetrics: () => ipcRenderer.invoke('executive:get-metrics'),
    subscribe: (cb: (snapshot: unknown) => void) => {
      const wrapped = (_event: unknown, snapshot: unknown) => cb(snapshot)
      ipcRenderer.on('runtime:executive-snapshot', wrapped)
      return () => ipcRenderer.removeListener('runtime:executive-snapshot', wrapped)
    }
  },
  capability: {
    getSnapshot: () => ipcRenderer.invoke('runtime:get-capability-snapshot'),
    getById: (id: string) => ipcRenderer.invoke('runtime:get-capability-by-id', id),
    getByCategory: (category: string) => ipcRenderer.invoke('runtime:get-capability-by-category', category)
  },
  execution: {
    getHistory: () => ipcRenderer.invoke('runtime:get-execution-history'),
    getExecution: (id: string) => ipcRenderer.invoke('runtime:get-execution', id),
    execute: (capabilityId: string, input: unknown, options?: unknown) =>
      ipcRenderer.invoke('runtime:execute-capability', capabilityId, input, options),
    cancel: (id: string) => ipcRenderer.invoke('runtime:cancel-execution', id),
    retry: (id: string) => ipcRenderer.invoke('runtime:retry-execution', id),
    subscribe: (cb: (event: unknown) => void) => {
      const wrapped = (_event: unknown, event: unknown) => cb(event)
      ipcRenderer.on('runtime:execution-event', wrapped)
      return () => ipcRenderer.removeListener('runtime:execution-event', wrapped)
    }
  },
  world: {
    getState: () => ipcRenderer.invoke('runtime:get-world-state')
  },
  cognitive: {
    getState: () => ipcRenderer.invoke('runtime:get-cognitive-state'),
    getAttention: () => ipcRenderer.invoke('runtime:get-attention-state'),
    getRelationship: () => ipcRenderer.invoke('runtime:get-relationship-state')
  },
  character: {
    getFrame: () => ipcRenderer.invoke('runtime:get-character-frame')
  },
  workspace: {
    getState: () => ipcRenderer.invoke('runtime:get-workspace-state'),
    getContext: () => ipcRenderer.invoke('runtime:get-workspace-context'),
    getSnapshot: () => ipcRenderer.invoke('runtime:get-workspace-snapshot'),
    setRootPath: (path: string) => ipcRenderer.invoke('runtime:workspace-set-root', path),
    getProject: (path: string) => ipcRenderer.invoke('runtime:get-workspace-project', path),
    getAllProjects: () => ipcRenderer.invoke('runtime:get-workspace-all-projects'),
    discover: (signals: unknown, mode: 'shallow' | 'deep') => ipcRenderer.invoke('runtime:workspace-discover', signals, mode),
    subscribe: (cb: (event: unknown) => void) => {
      const wrapped = (_event: unknown, event: unknown) => cb(event)
      ipcRenderer.on('runtime:workspace-event', wrapped)
      return () => ipcRenderer.removeListener('runtime:workspace-event', wrapped)
    }
  },
  filesystem: {
    getMetrics: () => ipcRenderer.invoke('filesystem:get-metrics')
  },
  vscode: {
    getSnapshot: () => ipcRenderer.invoke('vscode:get-snapshot'),
    getEditor: () => ipcRenderer.invoke('vscode:get-editor'),
    getWorkspaceFolders: () => ipcRenderer.invoke('vscode:get-workspace-folders'),
    getDiagnostics: () => ipcRenderer.invoke('vscode:get-diagnostics'),
    getGitStatus: () => ipcRenderer.invoke('vscode:get-git-status'),
    onEvent: (cb: (event: unknown) => void) => {
      const wrapped = (_event: unknown, event: unknown) => cb(event)
      ipcRenderer.on('vscode:event', wrapped)
      return () => ipcRenderer.removeListener('vscode:event', wrapped)
    }
  }
}

contextBridge.exposeInMainWorld('zaram', {
  isDesktop: true,
  ...runtimeAPI,
  app: {
    getInfo: () => ipcRenderer.invoke('app:get-info'),
    getVersion: () => ipcRenderer.invoke('app:get-version'),
    getPlatform: () => ipcRenderer.invoke('app:get-platform')
  },
  window: {
    maximize: () => ipcRenderer.invoke('app:maximize'),
    minimize: () => ipcRenderer.invoke('app:minimize'),
    restore: () => ipcRenderer.invoke('app:restore'),
    isMaximized: () => ipcRenderer.invoke('app:is-maximized'),
    quit: () => ipcRenderer.invoke('app:quit')
  },
  backend: {
    checkHealth: () => ipcRenderer.invoke('backend:health'),
    getStatus: () => ipcRenderer.invoke('backend:status')
  },
  dialog: {
    openFile: (options?: any) => ipcRenderer.invoke('dialog:open-file', options),
    saveFile: (options?: any) => ipcRenderer.invoke('dialog:save-file', options),
    selectDirectory: (options?: any) => ipcRenderer.invoke('dialog:select-directory', options)
  },
  notification: {
    show: (title: string, body: string) => ipcRenderer.invoke('notification:show', title, body)
  },
  shell: {
    openExternal: (url: string) => ipcRenderer.invoke('shell:open-external', url),
    openPath: (path: string) => ipcRenderer.invoke('shell:open-path', path)
  },
  clipboard: {
    readText: () => ipcRenderer.invoke('clipboard:read-text'),
    writeText: (text: string) => ipcRenderer.invoke('clipboard:write-text', text)
  },
  system: {
    getPlatform: () => ipcRenderer.invoke('system:platform'),
    getVersion: () => ipcRenderer.invoke('system:version'),
    getArch: () => ipcRenderer.invoke('system:arch')
  },
  settings: {
    get: (key: string) => ipcRenderer.invoke('settings:get', key),
    set: (key: string, value: any) => ipcRenderer.invoke('settings:set', key, value)
  },
  send: (channel: string, data?: any) => ipcRenderer.send(channel, data),
  receive: (channel: string, callback: (data: any) => void) => {
    ipcRenderer.on(channel, (_event, data) => callback(data))
  },
  invoke: (channel: string, ...args: any[]) => ipcRenderer.invoke(channel, ...args)
})

export type ZaramAPI = typeof runtimeAPI

  declare global {
    interface Window {
      zaram: {
        isDesktop: boolean
        presence: typeof runtimeAPI.presence
        executive: typeof runtimeAPI.executive
        capability: typeof runtimeAPI.capability
        execution: typeof runtimeAPI.execution
        world: typeof runtimeAPI.world
        cognitive: typeof runtimeAPI.cognitive
        character: typeof runtimeAPI.character
        workspace: {
          getState: () => Promise<any>
          getContext: () => Promise<any>
          getSnapshot: () => Promise<any>
          setRootPath: (path: string) => Promise<any>
          getProject: (path: string) => Promise<any>
          getAllProjects: () => Promise<any>
          discover: (signals: unknown, mode: 'shallow' | 'deep') => Promise<any>
          subscribe: (cb: (event: unknown) => void) => () => void
        }
        filesystem: {
          getMetrics: () => Promise<any>
        }
        vscode: {
          getSnapshot: () => Promise<any>
          getEditor: () => Promise<any>
          getWorkspaceFolders: () => Promise<any>
          getDiagnostics: () => Promise<any>
          getGitStatus: () => Promise<any>
        }
      } & {
        app: { getInfo: () => Promise<any>; getVersion: () => Promise<string>; getPlatform: () => Promise<string> }
        window: { maximize: () => Promise<void>; minimize: () => Promise<void>; restore: () => Promise<void>; isMaximized: () => Promise<boolean>; quit: () => Promise<void> }
        backend: { checkHealth: () => Promise<boolean>; getStatus: () => Promise<any> }
        dialog: { openFile: (options?: any) => Promise<any>; saveFile: (options?: any) => Promise<any>; selectDirectory: (options?: any) => Promise<any> }
        notification: { show: (title: string, body: string) => Promise<any> }
        shell: { openExternal: (url: string) => Promise<void>; openPath: (path: string) => Promise<any> }
        clipboard: { readText: () => Promise<string>; writeText: (text: string) => Promise<any> }
        system: { getPlatform: () => Promise<string>; getVersion: () => Promise<string>; getArch: () => Promise<string> }
        settings: { get: (key: string) => Promise<any>; set: (key: string, value: any) => Promise<any> }
        send: (channel: string, data?: any) => void
        receive: (channel: string, callback: (data: any) => void) => void
        invoke: (channel: string, ...args: any[]) => Promise<any>
      }
    }
  }
