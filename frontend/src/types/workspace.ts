export type PanelId = 'conversation' | 'artifacts' | 'orb' | 'diagnostics'

export interface PanelConfig {
  id: PanelId
  title: string
  visible: boolean
  width?: number
  height?: number
}

export interface WorkspaceLayout {
  panels: PanelConfig[]
  splitDirection: 'horizontal' | 'vertical'
}
