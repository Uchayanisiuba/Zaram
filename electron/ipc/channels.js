'use strict';

/**
 * Secure IPC channel catalogue.
 *
 * This module is the SINGLE SOURCE OF TRUTH for every IPC channel name. The
 * preload script may only invoke channels present in `RENDERER_INVOKABLE`,
 * which prevents a compromised renderer from calling arbitrary internal
 * channels. Main -> renderer push events live in `MAIN_EVENTS`.
 */

const Channels = {
  app: {
    getInfo: 'app:get-info',
    getVersion: 'app:get-version',
    getPlatform: 'app:get-platform',
  },
  os: {
    getInfo: 'os:get-info',
  },
  window: {
    minimize: 'window:minimize',
    maximize: 'window:maximize',
    restore: 'window:restore',
    close: 'window:close',
    reload: 'window:reload',
    isMaximized: 'window:is-maximized',
    setTitle: 'window:set-title',
  },
  backend: {
    getStatus: 'backend:get-status',
    restart: 'backend:restart',
  },
  notify: {
    show: 'notify:show',
  },
  dialog: {
    showOpen: 'dialog:show-open',
    showSave: 'dialog:save-file',
    showMessage: 'dialog:show-message',
    selectDirectory: 'dialog:select-directory',
  },
  shell: {
    openExternal: 'shell:open-external',
    openPath: 'shell:open-path',
    showItemInFolder: 'shell:show-item-in-folder',
  },
  clipboard: {
    readText: 'clipboard:read-text',
    writeText: 'clipboard:write-text',
  },
  fs: {
    getPath: 'fs:get-path',
    readText: 'fs:read-text',
    writeText: 'fs:write-text',
    listDir: 'fs:list-dir',
  },
  settings: {
    get: 'settings:get',
    set: 'settings:set',
    getAll: 'settings:get-all',
  },
  download: {
    start: 'download:start',
    cancel: 'download:cancel',
  },
  presence: {
    getStatus: 'presence:get-status',
    getDiagnostics: 'presence:get-diagnostics',
  },
  runtime: {
    getPresenceHealth: 'runtime:get-presence-health',
    getPresenceStatus: 'runtime:get-presence-status',
    getExecutiveSnapshot: 'runtime:get-executive-snapshot',
    getCapabilitySnapshot: 'runtime:get-capability-snapshot',
    getCapabilityById: 'runtime:get-capability-by-id',
    getCapabilityByCategory: 'runtime:get-capability-by-category',
    getExecutionHistory: 'runtime:get-execution-history',
    getExecution: 'runtime:get-execution',
    executeCapability: 'runtime:execute-capability',
    cancelExecution: 'runtime:cancel-execution',
    retryExecution: 'runtime:retry-execution',
    getWorldState: 'runtime:get-world-state',
    getCognitiveState: 'runtime:get-cognitive-state',
    getAttentionState: 'runtime:get-attention-state',
    getRelationshipState: 'runtime:get-relationship-state',
    getCharacterFrame: 'runtime:get-character-frame',
    executivePlan: 'executive:plan',
    executiveGetPlan: 'executive:get-plan',
    executiveGetConfidence: 'executive:get-confidence',
    executiveGetEvidence: 'executive:get-evidence',
    executiveGetMetrics: 'executive:get-metrics',
    workspaceGetState: 'workspace:get-state',
    workspaceGetContext: 'workspace:get-context',
    workspaceGetSnapshot: 'workspace:get-snapshot',
    workspaceSetRoot: 'workspace:set-root',
    workspaceDiscover: 'workspace:discover',
    workspaceGetAllProjects: 'workspace:get-all-projects',
    filesystemGetMetrics: 'filesystem:get-metrics',
    vscodeGetSnapshot: 'vscode:get-snapshot',
    vscodeGetEditor: 'vscode:get-editor',
    vscodeGetWorkspaceFolders: 'vscode:get-workspace-folders',
    vscodeGetDiagnostics: 'vscode:get-diagnostics',
    vscodeGetGitStatus: 'vscode:get-git-status',
    desktopGetSources: 'desktop:get-sources',
  },
};

/** Main process -> renderer push events (subscribed via ipcRenderer.on). */
const MAIN_EVENTS = {
  backendStatus: 'backend:status',
  downloadProgress: 'download:progress',
  updaterState: 'native:updater-state',
  deepLink: 'native:deep-link',
  fileOpen: 'native:file-open',
  log: 'desktop:log',
  presenceFrame: 'presence:frame',
  presenceViewport: 'presence:viewport',
  executiveSnapshot: 'runtime:executive-snapshot',
  executionEvent: 'runtime:execution-event',
  workspaceEvent: 'workspace:event',
  vscodeEvent: 'vscode:event',
};

/** Channels the renderer is permitted to invoke through the preload bridge. */
const RENDERER_INVOKABLE = [
  Channels.app.getInfo,
  Channels.app.getVersion,
  Channels.app.getPlatform,
  Channels.os.getInfo,
  Channels.window.minimize,
  Channels.window.maximize,
  Channels.window.restore,
  Channels.window.close,
  Channels.window.reload,
  Channels.window.isMaximized,
  Channels.window.setTitle,
  Channels.backend.getStatus,
  Channels.backend.restart,
  Channels.notify.show,
  Channels.dialog.showOpen,
  Channels.dialog.showSave,
  Channels.dialog.showMessage,
  Channels.dialog.selectDirectory,
  Channels.shell.openExternal,
  Channels.shell.openPath,
  Channels.shell.showItemInFolder,
  Channels.clipboard.readText,
  Channels.clipboard.writeText,
  Channels.fs.getPath,
  Channels.fs.readText,
  Channels.fs.writeText,
  Channels.fs.listDir,
  Channels.settings.get,
  Channels.settings.set,
  Channels.settings.getAll,
  Channels.download.start,
  Channels.download.cancel,
  Channels.presence.getStatus,
  Channels.presence.getDiagnostics,
  Channels.runtime.getPresenceHealth,
  Channels.runtime.getPresenceStatus,
  Channels.runtime.getExecutiveSnapshot,
  Channels.runtime.getCapabilitySnapshot,
  Channels.runtime.getCapabilityById,
  Channels.runtime.getCapabilityByCategory,
  Channels.runtime.getExecutionHistory,
  Channels.runtime.getExecution,
  Channels.runtime.executeCapability,
  Channels.runtime.cancelExecution,
  Channels.runtime.retryExecution,
  Channels.runtime.getWorldState,
  Channels.runtime.getCognitiveState,
  Channels.runtime.getAttentionState,
  Channels.runtime.getRelationshipState,
  Channels.runtime.getCharacterFrame,
  Channels.runtime.executivePlan,
  Channels.runtime.executiveGetPlan,
  Channels.runtime.executiveGetConfidence,
  Channels.runtime.executiveGetEvidence,
  Channels.runtime.executiveGetMetrics,
  Channels.runtime.workspaceGetState,
  Channels.runtime.workspaceGetContext,
  Channels.runtime.workspaceGetSnapshot,
  Channels.runtime.workspaceDiscover,
  Channels.runtime.workspaceGetAllProjects,
  Channels.runtime.workspaceSetRoot,
  Channels.runtime.filesystemGetMetrics,
  Channels.runtime.vscodeGetSnapshot,
  Channels.runtime.vscodeGetEditor,
  Channels.runtime.vscodeGetWorkspaceFolders,
  Channels.runtime.vscodeGetDiagnostics,
  Channels.runtime.vscodeGetGitStatus,
  Channels.runtime.desktopGetSources,
];

function listChannels() {
  const out = [];
  for (const group of Object.keys(Channels)) {
    for (const name of Object.keys(Channels[group])) {
      out.push(Channels[group][name]);
    }
  }
  return out;
}

function isInvokable(channel) {
  return RENDERER_INVOKABLE.includes(channel);
}

module.exports = { Channels, MAIN_EVENTS, RENDERER_INVOKABLE, listChannels, isInvokable };
