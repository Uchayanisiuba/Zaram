import type { Artifact, ArtifactType } from '@/types/artifacts';

export interface ArtifactViewerPlugin {
  type: ArtifactType;
  render: (artifact: Artifact, onUpdate?: (content: string) => void) => React.ReactNode;
  canEdit?: boolean;
}

class ViewerRegistry {
  private plugins: Map<ArtifactType, ArtifactViewerPlugin> = new Map();

  register(plugin: ArtifactViewerPlugin) {
    this.plugins.set(plugin.type, plugin);
  }

  get(type: ArtifactType): ArtifactViewerPlugin | undefined {
    return this.plugins.get(type);
  }

  getAll(): ArtifactViewerPlugin[] {
    return Array.from(this.plugins.values());
  }
}

export const viewerRegistry = new ViewerRegistry();
