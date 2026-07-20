'use strict';

const { contextBridge, ipcRenderer } = require('electron');
const { Channels, MAIN_EVENTS, isInvokable } = require('./ipc/channels');

/**
 * Secure preload.
 *
 * Runs in an isolated world. Exposes a single, curated `window.zaram` object.
 * Every invoke is validated against the RENDERER_INVOKABLE whitelist so a
 * compromised renderer cannot reach internal channels. No Node.js objects
 * (fs, child_process, require) are leaked to the page.
 */

function invoke(channel, ...args) {
  if (!isInvokable(channel)) {
    return Promise.reject(new Error(`IPC channel not allowed: ${channel}`));
  }
  return ipcRenderer.invoke(channel, ...args);
}

function subscribe(channel, listener) {
  const wrapped = (_event, ...args) => listener(...args);
  ipcRenderer.on(channel, wrapped);
  return () => ipcRenderer.removeListener(channel, wrapped);
}

const api = {
  isDesktop: true,
  app: {
    getInfo: () => invoke(Channels.app.getInfo),
    getVersion: () => invoke(Channels.app.getVersion),
    getPlatform: () => invoke(Channels.app.getPlatform),
  },
  os: {
    getInfo: () => invoke(Channels.os.getInfo),
  },
  window: {
    minimize: () => invoke(Channels.window.minimize),
    maximize: () => invoke(Channels.window.maximize),
    restore: () => invoke(Channels.window.restore),
    close: () => invoke(Channels.window.close),
    reload: () => invoke(Channels.window.reload),
    isMaximized: () => invoke(Channels.window.isMaximized),
    setTitle: (title) => invoke(Channels.window.setTitle, title),
  },
  backend: {
    getStatus: () => invoke(Channels.backend.getStatus),
    restart: () => invoke(Channels.backend.restart),
    onStatus: (listener) => subscribe(MAIN_EVENTS.backendStatus, listener),
  },
  notify: {
    show: (opts) => invoke(Channels.notify.show, opts),
  },
  dialog: {
    showOpen: (opts) => invoke(Channels.dialog.showOpen, opts),
    showSave: (opts) => invoke(Channels.dialog.showSave, opts),
    showMessage: (opts) => invoke(Channels.dialog.showMessage, opts),
    selectDirectory: (opts) => invoke(Channels.dialog.selectDirectory, opts),
  },
  shell: {
    openExternal: (url) => invoke(Channels.shell.openExternal, url),
    openPath: (path) => invoke(Channels.shell.openPath, path),
    showItemInFolder: (path) => invoke(Channels.shell.showItemInFolder, path),
  },
  clipboard: {
    readText: () => invoke(Channels.clipboard.readText),
    writeText: (text) => invoke(Channels.clipboard.writeText, text),
  },
  fs: {
    getPath: (name) => invoke(Channels.fs.getPath, name),
    readText: (name) => invoke(Channels.fs.readText, name),
    writeText: (name, content) => invoke(Channels.fs.writeText, name, content),
    listDir: (name) => invoke(Channels.fs.listDir, name),
  },
  settings: {
    get: (key) => invoke(Channels.settings.get, key),
    set: (key, value) => invoke(Channels.settings.set, key, value),
    getAll: () => invoke(Channels.settings.getAll),
  },
  download: {
    start: (url, opts) => invoke(Channels.download.start, url, opts),
    cancel: (id) => invoke(Channels.download.cancel, id),
    onProgress: (listener) => subscribe(MAIN_EVENTS.downloadProgress, listener),
  },
  presence: {
    getStatus: () => invoke(Channels.presence.getStatus),
    getDiagnostics: () => invoke(Channels.presence.getDiagnostics),
    onFrame: (listener) => subscribe(MAIN_EVENTS.presenceFrame, listener),
    onViewport: (listener) => subscribe(MAIN_EVENTS.presenceViewport, listener),
  },
  runtime: {
    getPresenceHealth: () => invoke(Channels.runtime.getPresenceHealth),
    getPresenceStatus: () => invoke(Channels.runtime.getPresenceStatus),
    getExecutiveSnapshot: () => invoke(Channels.runtime.getExecutiveSnapshot),
    getCapabilitySnapshot: () => invoke(Channels.runtime.getCapabilitySnapshot),
    getCapabilityById: (id) => invoke(Channels.runtime.getCapabilityById, id),
    getCapabilityByCategory: (category) => invoke(Channels.runtime.getCapabilityByCategory, category),
    getExecutionHistory: () => invoke(Channels.runtime.getExecutionHistory),
    getExecution: (id) => invoke(Channels.runtime.getExecution, id),
    executeCapability: (capabilityId, input, options) => invoke(Channels.runtime.executeCapability, capabilityId, input, options),
    cancelExecution: (id) => invoke(Channels.runtime.cancelExecution, id),
    retryExecution: (id) => invoke(Channels.runtime.retryExecution, id),
    getWorldState: () => invoke(Channels.runtime.getWorldState),
    getCognitiveState: () => invoke(Channels.runtime.getCognitiveState),
    getAttentionState: () => invoke(Channels.runtime.getAttentionState),
    getRelationshipState: () => invoke(Channels.runtime.getRelationshipState),
    getCharacterFrame: () => invoke(Channels.runtime.getCharacterFrame),
    desktopGetSources: (opts) => invoke(Channels.runtime.desktopGetSources, opts),
    onExecutiveSnapshot: (listener) => subscribe(MAIN_EVENTS.executiveSnapshot, listener),
    onExecutionEvent: (listener) => subscribe(MAIN_EVENTS.executionEvent, listener),
  },
  executive: {
    plan: (query) => invoke(Channels.runtime.executivePlan, query),
    getPlan: () => invoke(Channels.runtime.executiveGetPlan),
    getConfidence: () => invoke(Channels.runtime.executiveGetConfidence),
    getEvidence: () => invoke(Channels.runtime.executiveGetEvidence),
    getMetrics: () => invoke(Channels.runtime.executiveGetMetrics),
  },
  workspace: {
    getState: () => invoke(Channels.runtime.workspaceGetState),
    getContext: () => invoke(Channels.runtime.workspaceGetContext),
    getSnapshot: () => invoke(Channels.runtime.workspaceGetSnapshot),
    setRootPath: (rootPath) => invoke(Channels.runtime.workspaceSetRoot, rootPath),
    discover: (signals, mode) => invoke(Channels.runtime.workspaceDiscover, signals, mode),
    getAllProjects: () => invoke(Channels.runtime.workspaceGetAllProjects),
    onEvent: (listener) => subscribe(MAIN_EVENTS.workspaceEvent, listener),
  },
  filesystem: {
    getMetrics: () => invoke(Channels.runtime.filesystemGetMetrics),
  },
  vscode: {
    getSnapshot: () => invoke(Channels.runtime.vscodeGetSnapshot),
    getEditor: () => invoke(Channels.runtime.vscodeGetEditor),
    getWorkspaceFolders: () => invoke(Channels.runtime.vscodeGetWorkspaceFolders),
    getDiagnostics: () => invoke(Channels.runtime.vscodeGetDiagnostics),
    getGitStatus: () => invoke(Channels.runtime.vscodeGetGitStatus),
    onEvent: (listener) => subscribe(MAIN_EVENTS.vscodeEvent, listener),
  },
};

contextBridge.exposeInMainWorld('zaram', api);
