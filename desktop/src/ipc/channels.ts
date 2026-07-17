export const DESKTOP_CHANNELS = {
  WINDOW: 'window',
  NOTIFICATION: 'notification',
  SHELL: 'shell',
  FILE_DIALOG: 'file-dialog',
  DOWNLOAD: 'download',
  SETTINGS: 'settings',
  BACKEND: 'backend',
  CLIPBOARD: 'clipboard',
  SYSTEM: 'system',
  RUNTIME: 'runtime',
  PRESENCE: 'presence',
  WORKSPACE: 'workspace',
  VSCODE: 'vscode'
} as const

export interface RuntimeRequest {
  action: string
  payload?: unknown
}

export interface RuntimeResponse<T = unknown> {
  success: boolean
  data?: T
  error?: string
}
