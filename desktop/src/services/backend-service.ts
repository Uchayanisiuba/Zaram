import { ChildProcess, spawn } from 'child_process'
import path from 'path'
import fs from 'fs'
import { getBackendPath, getAppDataPath } from '../config/paths'
import { isDevelopment } from '../config/environment'

export interface BackendServiceOptions {
  host?: string
  port?: number
  pythonPath?: string
  backendScript?: string
  autoStart?: boolean
  healthCheckInterval?: number
}

export interface BackendStatus {
  running: boolean
  process?: ChildProcess
  port?: number
  host?: string
  pid?: number
  error?: string
}

const DEFAULT_BACKEND_PORT = 8000
const DEFAULT_HEALTH_CHECK_INTERVAL = 5000
const DEFAULT_BACKEND_SCRIPT = path.join(__dirname, '..', '..', '..', 'backend', 'main.py')

export class BackendService {
  private process: ChildProcess | null = null
  private status: BackendStatus = {
    running: false,
    host: '127.0.0.1',
    port: DEFAULT_BACKEND_PORT
  }
  private healthCheckTimer: NodeJS.Timeout | null = null
  private healthCheckInterval: number
  private options: BackendServiceOptions

  constructor(options: BackendServiceOptions = {}) {
    this.options = {
      host: options.host || '127.0.0.1',
      port: options.port || DEFAULT_BACKEND_PORT,
      pythonPath: options.pythonPath || 'python',
      backendScript: options.backendScript || DEFAULT_BACKEND_SCRIPT,
      autoStart: options.autoStart ?? true,
      healthCheckInterval: options.healthCheckInterval || DEFAULT_HEALTH_CHECK_INTERVAL
    }
    this.healthCheckInterval = this.options.healthCheckInterval!

    this.status.host = this.options.host!
    this.status.port = this.options.port!
  }

  async start(): Promise<BackendStatus> {
    if (this.status.running) {
      return this.status
    }

    try {
      if (isDevelopment()) {
        await this.startDevelopment()
      } else {
        await this.startProduction()
      }

      this.status.running = true
      this.startHealthCheck()
      return this.status
    } catch (error) {
      this.status.error = error instanceof Error ? error.message : String(error)
      return this.status
    }
  }

  private async startDevelopment(): Promise<void> {
    return new Promise((resolve, reject) => {
      const script = this.options.backendScript!
      if (!fs.existsSync(script)) {
        reject(new Error(`Backend script not found: ${script}`))
        return
      }

      const args = [script]
      const env = {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        USE_NEW_KERNEL: 'true'
      }

      this.process = spawn(this.options.pythonPath!, args, {
        env,
        cwd: path.join(__dirname, '..', '..', '..', 'backend'),
        stdio: 'pipe'
      })

      this.process.stdout?.on('data', (data) => {
        console.log(`[Backend] ${data.toString()}`)
      })

      this.process.stderr?.on('data', (data) => {
        console.error(`[Backend] ${data.toString()}`)
      })

      this.process.on('error', (error) => {
        reject(error)
      })

      this.process.on('spawn', () => {
        this.status.pid = this.process!.pid!
        resolve()
      })

      this.process.on('exit', (code) => {
        if (code !== 0 && this.status.running) {
          this.status.running = false
          this.status.error = `Backend exited with code ${code}`
        }
      })
    })
  }

  private async startProduction(): Promise<void> {
    const backendPath = getBackendPath()
    if (!fs.existsSync(backendPath)) {
      throw new Error(`Backend executable not found: ${backendPath}`)
    }

    return new Promise((resolve, reject) => {
      this.process = spawn(backendPath, [], {
        stdio: 'pipe',
        cwd: getAppDataPath()
      })

      this.process.stdout?.on('data', (data) => {
        console.log(`[Backend] ${data.toString()}`)
      })

      this.process.stderr?.on('data', (data) => {
        console.error(`[Backend] ${data.toString()}`)
      })

      this.process.on('error', (error) => {
        reject(error)
      })

      this.process.on('spawn', () => {
        this.status.pid = this.process!.pid!
        resolve()
      })

      this.process.on('exit', (code) => {
        if (code !== 0 && this.status.running) {
          this.status.running = false
          this.status.error = `Backend exited with code ${code}`
        }
      })
    })
  }

  async stop(): Promise<void> {
    this.stopHealthCheck()

    if (this.process) {
      this.status.running = false
      this.process.kill('SIGTERM')
      this.process = null
    }
  }

  async checkHealth(): Promise<boolean> {
    try {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 3000)

      const response = await fetch(`http://${this.status.host}:${this.status.port}/health`, {
        signal: controller.signal as any
      })

      clearTimeout(timeout)
      return response.ok
    } catch {
      return false
    }
  }

  getStatus(): BackendStatus {
    return { ...this.status }
  }

  private startHealthCheck(): void {
    this.stopHealthCheck()
    this.healthCheckTimer = setInterval(async () => {
      const healthy = await this.checkHealth()
      if (!healthy && this.status.running) {
        console.error('Backend health check failed')
        this.status.running = false
        this.status.error = 'Backend health check failed'
      }
    }, this.healthCheckInterval)
  }

  private stopHealthCheck(): void {
    if (this.healthCheckTimer) {
      clearInterval(this.healthCheckTimer)
      this.healthCheckTimer = null
    }
  }
}
