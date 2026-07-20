// desktop/src/capabilities/plugins/plugin-capability.ts
//
// Milestone 4.0 — Plugin Capability Pack.
// Placeholder for future plugin marketplace.

import type { ICapabilityRuntime } from '../../runtime/capability'
import type { IExecutionInvoker } from '../../runtime/execution'
import type { PluginManifest } from './plugin-types'

const PLUGIN_CAPABILITIES: PluginManifest[] = [
  { id: 'vscode', name: 'VS Code', version: '0.1.0', description: 'Visual Studio Code integration', author: 'Zaram', category: 'developer', permissions: [], capabilities: [] },
  { id: 'unreal', name: 'Unreal Engine', version: '0.1.0', description: 'Unreal Engine integration', author: 'Zaram', category: 'developer', permissions: [], capabilities: [] },
  { id: 'blender', name: 'Blender', version: '0.1.0', description: 'Blender integration', author: 'Zaram', category: 'developer', permissions: [], capabilities: [] },
]

export class PluginCapabilityPack {
  constructor(private readonly capabilityRuntime: ICapabilityRuntime) {}

  registerHandlers(_invoker: IExecutionInvoker): void {
    // Plugins are not yet available in Alpha.
  }

  registerDescriptors(capabilityRuntime: ICapabilityRuntime): void {
    // Plugins are not yet available in Alpha.
  }
}
