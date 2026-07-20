// desktop/src/capabilities/plugins/plugin-types.ts
//
// Milestone 4.0 — Plugin Architecture types.
// Placeholder for future plugin system.

export interface PluginManifest {
  id: string
  name: string
  version: string
  description: string
  author: string
  category: 'developer' | 'creator' | 'business' | 'research' | 'automation'
  permissions: string[]
  capabilities: string[]
}

export interface PluginRuntime {
  manifest: PluginManifest
  initialize(): Promise<void>
  shutdown(): Promise<void>
}
