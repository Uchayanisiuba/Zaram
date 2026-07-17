import { app } from 'electron'
import path from 'path'
import os from 'os'

export const getAppDataPath = (): string => {
  const platform = process.platform
  const appName = 'Zaram'

  switch (platform) {
    case 'win32':
      return path.join(os.homedir(), 'AppData', 'Local', appName)
    case 'darwin':
      return path.join(os.homedir(), 'Library', 'Application Support', appName)
    case 'linux':
      return path.join(os.homedir(), '.config', appName)
    default:
      return path.join(os.homedir(), `.${appName.toLowerCase()}`)
  }
}

export const getBackendPath = (): string => {
  const platform = process.platform
  const appData = getAppDataPath()

  switch (platform) {
    case 'win32':
      return path.join(appData, 'backend', 'main.exe')
    case 'darwin':
      return path.join(appData, 'backend', 'main')
    case 'linux':
      return path.join(appData, 'backend', 'main')
    default:
      return path.join(appData, 'backend', 'main')
  }
}

export const getResourcesPath = (): string => {
  if (app.isPackaged) {
    return path.join(process.resourcesPath)
  }
  return path.join(__dirname, '..', 'resources')
}

export const getFrontendDistPath = (): string => {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'frontend')
  }
  return path.join(__dirname, '..', '..', '..', 'frontend', 'dist')
}

export const getSplashPath = (): string => {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'splash.html')
  }
  return path.join(__dirname, '..', '..', 'resources', 'splash.html')
}

export const isDevelopment = (): boolean => {
  return !app.isPackaged
}

export const isWindows = (): boolean => {
  return process.platform === 'win32'
}

export const isMacOS = (): boolean => {
  return process.platform === 'darwin'
}

export const isLinux = (): boolean => {
  return process.platform === 'linux'
}

export const getPlatformName = (): string => {
  return process.platform
}
