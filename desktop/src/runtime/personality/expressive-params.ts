import { DEFAULT_EXPRESSIVE_PARAMS, ExpressiveParams } from '../types'
import { IExpressiveParamsSource } from '../interfaces'

export class DefaultExpressiveParamsSource implements IExpressiveParamsSource {
  private params: ExpressiveParams
  private readonly listeners = new Set<(params: ExpressiveParams) => void>()

  constructor(initial: ExpressiveParams = DEFAULT_EXPRESSIVE_PARAMS) {
    this.params = { ...initial }
  }

  getExpressiveParams(): ExpressiveParams {
    return { ...this.params }
  }

  setExpressiveParams(params: Partial<ExpressiveParams>): void {
    this.params = { ...this.params, ...params }
    const snapshot = { ...this.params }
    this.listeners.forEach((listener) => listener(snapshot))
  }

  subscribe(listener: (params: ExpressiveParams) => void): () => void {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }
}
