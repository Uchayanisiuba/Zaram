'use strict';

/**
 * @typedef {Object} DesktopConfig
 * @property {boolean} isDev
 * @property {string} appPath
 * @property {string} resourcesPath
 * @property {string} userDataPath
 * @property {string} logsPath
 * @property {string} settingsPath
 * @property {string} windowStatePath
 * @property {object} backend
 * @property {object} renderer
 * @property {object} window
 */

/**
 * @typedef {Object} Logger
 * @property {(msg: string, meta?: object) => void} debug
 * @property {(msg: string, meta?: object) => void} info
 * @property {(msg: string, meta?: object) => void} warn
 * @property {(msg: string, meta?: object) => void} error
 * @property {(scope: string) => Logger} child
 */

/**
 * @typedef {Object} BackendStatus
 * @property {'starting'|'available'|'unavailable'|'restarting'|'error'} state
 * @property {string} [url]
 * @property {number} [lastCheckedAt]
 * @property {string} [error]
 */

/**
 * @typedef {Object} NotificationOptions
 * @property {string} title
 * @property {string} [body]
 * @property {string} [icon]
 */

/**
 * Service contracts. These are the desktop abstractions exposed (eventually)
 * to runtimes via the secure IPC bridge. Implementations live in ./services.
 */

/**
 * @typedef {Object} WindowService
 * @property {() => void} minimize
 * @property {() => void} maximize
 * @property {() => void} restore
 * @property {() => void} close
 * @property {() => void} reload
 * @property {() => boolean} isMaximized
 * @property {(title: string) => void} setTitle
 */

/**
 * @typedef {Object} NotificationService
 * @property {(opts: NotificationOptions) => Promise<string|null>} show
 */

/**
 * @typedef {Object} ShellService
 * @property {(url: string) => Promise<void>} openExternal
 * @property {(path: string) => Promise<string>} openPath
 * @property {(path: string) => void} showItemInFolder
 */

/**
 * @typedef {Object} FileDialogService
 * @property {(opts?: object) => Promise<string|null>} showOpen
 * @property {(opts?: object) => Promise<string|null>} showSave
 * @property {(opts?: object) => Promise<void>} showMessage
 */

/**
 * @typedef {Object} DownloadService
 * @property {(url: string, opts?: object) => Promise<string>} start
 * @property {(id: string) => void} cancel
 */

/**
 * @typedef {Object} SettingsService
 * @property {(key: string) => any} get
 * @property {(key: string, value: any) => void} set
 * @property {() => object} getAll
 */

module.exports = {};
