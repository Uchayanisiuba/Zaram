export interface DesktopService {
  initialize(): Promise<void>
  shutdown(): Promise<void>
}

export interface WindowService extends DesktopService {
  maximize(): void
  minimize(): void
  restore(): void
  isMaximized(): boolean
  getState(): { width: number; height: number; isMaximized: boolean }
}

export interface NotificationService extends DesktopService {
  show(title: string, body: string): Promise<{ success: boolean; error?: string }>
}

export interface ShellService extends DesktopService {
  openExternal(url: string): Promise<{ success: boolean }>
  openPath(filePath: string): Promise<{ success: boolean }>
}

export interface FileDialogService extends DesktopService {
  openFile(options?: any): Promise<{ success: boolean; filePaths?: string[]; canceled?: boolean }>
  saveFile(options?: any): Promise<{ success: boolean; filePath?: string; canceled?: boolean }>
  selectDirectory(options?: any): Promise<{ success: boolean; filePaths?: string[]; canceled?: boolean }>
}

export interface DownloadService extends DesktopService {
  download(url: string, savePath?: string): Promise<{ success: boolean; path?: string; error?: string }>
  cancel(id: string): Promise<{ success: boolean }>
}

export interface SettingsService extends DesktopService {
  get<T>(key: string, defaultValue?: T): Promise<T | null>
  set(key: string, value: any): Promise<{ success: boolean; error?: string }>
}
