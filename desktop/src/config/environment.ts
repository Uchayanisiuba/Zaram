export const ENV = {
  DEV: 'development',
  PRODUCTION: 'production',
  TEST: 'test'
} as const

export type Environment = typeof ENV[keyof typeof ENV]

let currentEnv: Environment = ENV.PRODUCTION

export const setEnvironment = (env: Environment): void => {
  currentEnv = env
}

export const getEnvironment = (): Environment => {
  return currentEnv
}

export const isDevelopment = (): boolean => {
  return currentEnv === ENV.DEV
}

export const isProduction = (): boolean => {
  return currentEnv === ENV.PRODUCTION
}

export const isTest = (): boolean => {
  return currentEnv === ENV.TEST
}
