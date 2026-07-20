export type PanelId = 'conversation' | 'artifacts' | 'orb' | 'diagnostics' | 'terminal' | 'notes' | 'browser';

export interface PanelConfig {
  id: PanelId;
  title: string;
  visible: boolean;
  width?: number;
  height?: number;
  minWidth?: number;
  minHeight?: number;
}

export interface WorkspaceLayout {
  panels: PanelConfig[];
  activePanelId?: PanelId;
  splitDirection?: 'horizontal' | 'vertical';
}
