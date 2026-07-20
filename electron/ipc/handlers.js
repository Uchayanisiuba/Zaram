'use strict';

const os = require('os');
const { Channels } = require('./channels');

/**
 * Registers every IPC handler on the main process. Each handler delegates to a
 * desktop service from the injected container. Errors are logged and propagated
 * to the renderer as rejected promises (never swallowed silently).
 *
 * @param {import('electron').IpcMain} ipcMain
 * @param {object} ctx
 * @param {ReturnType<typeof require('../services/index').createServices>} ctx.services
 * @param {import('electron').App} ctx.app
 * @param {import('../types').DesktopConfig} ctx.config
 * @param {import('../backend/backendLauncher').BackendLauncher} ctx.backend
 * @param {import('../types').Logger} [ctx.logger]
 */
function registerHandlers(ipcMain, ctx) {
  const { services, app, config, backend, logger } = ctx;
  const log = logger || console;

  function handle(channel, fn) {
    ipcMain.handle(channel, async (_event, ...args) => {
      try {
        return await fn(...args);
      } catch (err) {
        log.warn('IPC handler error', { channel, error: err.message });
        throw err;
      }
    });
  }

  handle(Channels.app.getInfo, () => ({
    name: 'Zaram',
    version: app.getVersion(),
    platform: process.platform,
    isDev: config.isDev,
  }));
  handle(Channels.app.getVersion, () => app.getVersion());
  handle(Channels.app.getPlatform, () => process.platform);

  handle(Channels.os.getInfo, () => ({
    platform: process.platform,
    arch: os.arch(),
    release: os.release(),
    cpus: os.cpus().length,
    totalMemory: os.totalmem(),
    freeMemory: os.freemem(),
  }));

  handle(Channels.window.minimize, () => services.window.minimize());
  handle(Channels.window.maximize, () => services.window.maximize());
  handle(Channels.window.restore, () => services.window.restore());
  handle(Channels.window.close, () => services.window.close());
  handle(Channels.window.reload, () => services.window.reload());
  handle(Channels.window.isMaximized, () => services.window.isMaximized());
  handle(Channels.window.setTitle, (title) => services.window.setTitle(title));

    handle(Channels.backend.getStatus, () => backend.getStatus());
  handle(Channels.backend.restart, () => backend.restart());

  handle(Channels.notify.show, (opts) => services.notification.show(opts));

  handle(Channels.dialog.showOpen, (opts) => services.dialog.showOpen(opts));
  handle(Channels.dialog.showSave, (opts) => services.dialog.showSave(opts));
  handle(Channels.dialog.showMessage, (opts) => services.dialog.showMessage(opts));
  handle(Channels.dialog.selectDirectory, (opts) => services.dialog.selectDirectory(opts));

  handle(Channels.shell.openExternal, (url) => services.shell.openExternal(url));
  handle(Channels.shell.openPath, (p) => services.shell.openPath(p));
  handle(Channels.shell.showItemInFolder, (p) => services.shell.showItemInFolder(p));

  handle(Channels.clipboard.readText, () => require('electron').clipboard.readText());
  handle(Channels.clipboard.writeText, (text) => require('electron').clipboard.writeText(text));

  handle(Channels.fs.getPath, (name) => services.fs.getPath(name));
  handle(Channels.fs.readText, (root, rel) => services.fs.readText(root, rel));
  handle(Channels.fs.writeText, (root, rel, content) => services.fs.writeText(root, rel, content));
  handle(Channels.fs.listDir, (root, rel) => services.fs.listDir(root, rel));

  handle(Channels.settings.get, (key) => services.settings.get(key));
  handle(Channels.settings.set, (key, value) => services.settings.set(key, value));
  handle(Channels.settings.getAll, () => services.settings.getAll());

  handle(Channels.download.start, (url, opts) => services.downloads.start(url, opts));
  handle(Channels.download.cancel, (id) => services.downloads.cancel(id));

  async function fetchWithRetry(url, options = {}, retries = 3) {
    for (let i = 0; i < retries; i++) {
      try {
        const res = await fetch(url, options);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res;
      } catch (err) {
        if (i === retries - 1) throw err;
        await new Promise(r => setTimeout(r, 1000 * (i + 1)));
      }
    }
  }

  handle(Channels.presence.getStatus, async () => {
    const res = await fetchWithRetry(`${backend.config.backend.baseUrl}/api/presence/status`);
    if (!res.ok) throw new Error(`Presence status failed: ${res.status}`);
    return res.json();
  });
  handle(Channels.presence.getDiagnostics, async () => {
    const res = await fetchWithRetry(`${backend.config.backend.baseUrl}/api/presence/diagnostics`);
    if (!res.ok) throw new Error(`Presence diagnostics failed: ${res.status}`);
    return res.json();
  });

  if (ctx.desktopRuntime) {
    const rt = ctx.desktopRuntime;
    const getCap = () => rt.container.resolve('capabilityRuntime');
    const getExec = () => rt.container.resolve('executionRuntime');
    const getExecutive = () => rt.container.resolve('executiveRuntime');
    const getWorkspace = () => rt.container.resolve('workspaceRuntime');
    const getFilesystem = () => rt.container.resolve('filesystemPack');
    const getVSCode = () => rt.container.resolve('vscodePack');

    handle(Channels.runtime.getPresenceHealth, () => rt.presenceRuntime.getHealth());
    handle(Channels.runtime.getPresenceStatus, () => ({
      status: rt.presenceRuntime.getStatus(),
      health: rt.presenceRuntime.getHealth(),
      frameRate: rt.presenceRuntime.getFrameRate(),
      animationConnection: rt.presenceRuntime.getAnimationConnection()
    }));
    handle(Channels.runtime.getExecutiveSnapshot, () => rt.presenceRuntime.getExecutiveSnapshot?.());
    handle(Channels.runtime.getCapabilitySnapshot, () => getCap()?.getSnapshot?.());
    handle(Channels.runtime.getCapabilityById, (_e, id) => getCap()?.get?.(id) ?? null);
    handle(Channels.runtime.getCapabilityByCategory, (_e, cat) => getCap()?.getByCategory?.(cat) ?? []);
    handle(Channels.runtime.getExecutionHistory, () => getExec()?.getHistory?.() ?? []);
    handle(Channels.runtime.getExecution, (_e, id) => getExec()?.getExecution?.(id) ?? null);
    handle(Channels.runtime.executeCapability, async (_e, capabilityId, input, options) => {
      try {
        console.log('[IPC] executeCapability called:', capabilityId, 'input:', input)
        const id = getExec().execute({
          capabilityId,
          input,
          context: {
            correlationId: `ui-${Date.now()}`,
            grantedPermissions: [],
            actor: 'ui',
            createdAt: Date.now()
          },
          options
        });
        console.log('[IPC] executeCapability returned id:', id)
        return { success: true, id };
      } catch (error) {
        console.error('[IPC] executeCapability error:', error)
        return { success: false, error: String(error) };
      }
    });
    handle(Channels.runtime.cancelExecution, (_e, id) => getExec()?.cancel?.(id) ?? false);
    handle(Channels.runtime.retryExecution, (_e, id) => getExec()?.retry?.(id) ?? false);
    handle(Channels.runtime.getWorldState, () => rt.presenceRuntime.getWorldState?.());
    handle(Channels.runtime.getCognitiveState, () => rt.presenceRuntime.getCognitiveState?.());
    handle(Channels.runtime.getAttentionState, () => rt.presenceRuntime.getAttentionState?.());
    handle(Channels.runtime.getRelationshipState, () => rt.presenceRuntime.getRelationshipState?.());
    handle(Channels.runtime.getCharacterFrame, () => rt.presenceRuntime.getCharacterFrame?.());

    handle(Channels.runtime.executivePlan, (_e, query) => {
      console.log('[IPC] executive:plan called with:', query)
      const result = getExecutive()?.plan?.(query) ?? null
      console.log('[IPC] executive:plan returned:', result)
      return result
    })
    handle(Channels.runtime.executiveGetPlan, () => getExecutive()?.getCurrentPlan?.() ?? null);
    handle(Channels.runtime.executiveGetConfidence, () => getExecutive()?.getConfidence?.() ?? 0);
    handle(Channels.runtime.executiveGetEvidence, () => getExecutive()?.getEvidence?.() ?? []);
    handle(Channels.runtime.executiveGetMetrics, () => getExecutive()?.getCapabilityMetrics?.() ?? []);

    handle(Channels.runtime.workspaceGetState, () => getWorkspace()?.getWorkspaceState?.());
    handle(Channels.runtime.workspaceGetContext, () => getWorkspace()?.getWorkspaceContext?.());
    handle(Channels.runtime.workspaceGetSnapshot, () => getWorkspace()?.getWorkspaceSnapshot?.());
    handle(Channels.runtime.workspaceDiscover, async (_e, signals, mode) => {
      try {
        await getWorkspace()?.discover?.(signals, mode);
        return { success: true };
      } catch (error) {
        return { success: false, error: String(error) };
      }
    });
    handle(Channels.runtime.workspaceGetAllProjects, () => getWorkspace()?.getAllProjects?.() ?? []);
    handle(Channels.runtime.workspaceSetRoot, (_e, rootPath) => {
      if (getWorkspace()?.setRootPath) {
        getWorkspace().setRootPath(rootPath);
        return { success: true, rootPath };
      }
      return { success: false, error: 'Workspace runtime unavailable' };
    });

    handle(Channels.runtime.filesystemGetMetrics, () => getFilesystem()?.getMetrics?.());

    handle(Channels.runtime.vscodeGetSnapshot, () => getVSCode()?.getAdapter?.().getSnapshot?.());
    handle(Channels.runtime.vscodeGetEditor, () => getVSCode()?.getAdapter?.().getEditorInfo?.());
    handle(Channels.runtime.vscodeGetWorkspaceFolders, () => getVSCode()?.getAdapter?.().getWorkspaceFolders?.());
    handle(Channels.runtime.vscodeGetDiagnostics, () => getVSCode()?.getAdapter?.().getDiagnostics?.());
    handle(Channels.runtime.vscodeGetGitStatus, () => getVSCode()?.getAdapter?.().getGitStatus?.());

    handle(Channels.runtime.desktopGetSources, async (_e, opts) => {
      try {
        const { desktopCapturer } = require('electron');
        const sources = await desktopCapturer.getSources(opts || { types: ['window', 'screen'] });
        return sources.map(s => ({ id: s.id, name: s.name, thumbnail: s.thumbnail?.toDataURL() }));
      } catch (error) {
        return [];
      }
    });
  }
}

module.exports = { registerHandlers };
