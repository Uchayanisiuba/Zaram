declare module '*.css' {
  const content: string
  export default content
}

declare module 'react-syntax-highlighter' {
  const ReactMarkdown: React.ComponentType<any>
  export default ReactMarkdown
}

declare module 'react-syntax-highlighter/dist/esm/styles/prism' {
  const content: Record<string, any>
  export default content
}

declare module 'vitest' {
  export const describe: any
  export const it: any
  export const expect: any
  export const vi: any
}

declare module '@stores/artifactStore' {
  export const useArtifactStore: any
}

declare module '@stores/chatStore' {
  export const useChatStore: any
}

declare module '@stores/themeStore' {
  export const useThemeStore: any
}

declare module '@stores/modelStore' {
  export const useModelStore: any
}

declare module '@stores/api' {
  export const api: any
}

declare module '@types' {
  export interface Artifact { id: string; name: string; type: string; content: string }
  export interface WorkspaceState { panels: any[] }
  export type PanelId = string
  export interface PanelConfig { id: PanelId; type: string }
  export interface WorkspaceLayout { panels: PanelConfig[] }
}

declare module '@lib/utils' {
  export function cn(...classes: any[]): string
}

declare module '@/context/ZaramContext' {
  export function useZaram(): any
  export const ZaramProvider: any
}
