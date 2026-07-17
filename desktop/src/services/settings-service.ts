import { app } from 'electron'
import path from 'path'
import fs from 'fs'
import { SettingsService } from './desktop-service'

export class SettingsServiceImpl implements SettingsService {
  private settingsPath: string
  private cache: Map<string, any> = new Map()

  constructor() {
    this.settingsPath = path.join(app.getPath('userData'), 'settings.json')
    this.load()
  }

  async initialize(): Promise<void> {
    // Settings loaded in constructor
  }

  async shutdown(): Promise<void> {
    this.save()
  }

  async get<T>(key: string, defaultValue?: T): Promise<T | null> {
    if (this.cache.has(key)) {
      return this.cache.get(key) as T
    }
    if (defaultValue !== undefined) {
      return defaultValue
    }
    return null
  }

  async set(key: string, value: any): Promise<{ success: boolean; error?: string }> {
    try {
      this.cache.set(key, value)
      this.save()
      return { success: true }
    } catch (error) {
      return { success: false, error: String(error) }
    }
  }

  private load(): void {
    try {
      if (fs.existsSync(this.settingsPath)) {
        const data = JSON.parse(fs.readFileSync(this.settingsPath, 'utf-8'))
        for (const [key, value] of Object.entries(data)) {
          this.cache.set(key, value)
        }
      }
    } catch (error) {
      console.error('Failed to load settings:', error)
    }
  }

  private save(): void {
    try {
      const dir = path.dirname(this.settingsPath)
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true })
      }
      const data: Record<string, any> = {}
      for (const [key, value] of this.cache) {
        data[key] = value
      }
      fs.writeFileSync(this.settingsPath, JSON.stringify(data, null, 2), 'utf-8')
    } catch (error) {
      console.error('Failed to save settings:', error)
    }
  }
}
