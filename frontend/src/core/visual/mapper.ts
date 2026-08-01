/**
 * ZARAM CONSTITUTIONAL COMPLIANCE:
 * This file operates strictly in Stage 4 (Visual) of the 4-Stage Pipeline.
 * PROHIBITED: Importing React, Three.js, or Semantic/Memory/AI logic.
 * RULE: This is a pure stateless mapper. It consumes SimulationState, FrameState, and VisualTheme
 * to produce VisualState. It never mutates the Semantic Graph or Simulation State.
 * See: 00_ZARAM_CONSTITUTION/RuntimeModel.md
 */
// frontend/src/core/visual/mapper.ts
import { SpatialGraph, KnowledgeArchetype, NEIGHBORHOODS } from '../semantic/types';
import { SimulationState } from '../simulation/types';
import { FrameState } from '../frame/types';
import { VisualTheme, VisualState, VisualNode, VisualEdge, RuntimeSignature, ARCHETYPE_VISUAL_DEFAULTS, NeighborhoodVisualState } from './types';
import { PresenceState as PresenceStateType } from '../../theme/presenceTheme';
import { PRESENCE_COLORS } from '../../theme/presenceTheme';

const HEAT_DECAY_RATE = 0.001;

interface MapperContext {
  illuminatedNodeIds: Set<string>;
  activeClusterIds: Set<string>;
  presenceState: PresenceStateType;
  presenceIntensity: number;
  currentTime: number;
  searchQuery: string;
  searchResults: Set<string>;
  energyFlows: Map<string, number>;
}

export function mapToVisualState(
  graph: SpatialGraph,
  simulation: SimulationState,
  frame: FrameState,
  theme: VisualTheme,
  context: MapperContext
): VisualState {
  const {
    illuminatedNodeIds,
    activeClusterIds,
    presenceState,
    currentTime = Date.now(),
    searchQuery,
    searchResults,
    energyFlows,
  } = context;

  const presenceGlow = (PRESENCE_COLORS[presenceState] || PRESENCE_COLORS.Idle).glow;

  // Defensive: guard against null/undefined simulation nodes and frame
  const simNodes = simulation.nodes ?? [];
  const frameVisual = frame.visual ?? { presence: 0.5, energy: 0.3, focus: 0.5, activity: 0.1 };

  const visualNodes: VisualNode[] = graph.nodes.map(node => {
    const simNode = simNodes.find(s => s.id === node.id);
    if (!simNode) return null;

    const archetype = node.archetype || node.type as KnowledgeArchetype;
    const archetypeDefaults = ARCHETYPE_VISUAL_DEFAULTS[archetype];
    const baseColor = archetypeDefaults?.baseColor || theme.nodeStyles[node.type]?.color || '#ffffff';

    const signature: RuntimeSignature = (node.metadata?.runtimeSignature as RuntimeSignature) || 'default';
    const signatureColor = theme.signatureColors[signature];

    const lastAccessed = node.metadata?.lastAccessed || 0;
    const timeSinceAccess = currentTime - lastAccessed;
    const heat = Math.max(0, 1 - (timeSinceAccess * HEAT_DECAY_RATE));

    const confidence = node.metadata?.confidence ?? 0.8;

    const isIlluminated = illuminatedNodeIds.has(node.id);
    const isActiveCluster = node.clusterId && activeClusterIds.has(node.clusterId);
    const isSearchResult = searchResults.has(node.id);
    const isSearchMatch = searchQuery && node.label.toLowerCase().includes(searchQuery.toLowerCase());
    const isDimmed = searchQuery && !isSearchMatch && !isSearchResult;

    const energyFlow = energyFlows.get(node.id) || 0;
    const presenceReactivity = node.presenceReactivity ?? 0.5;

    let emissiveIntensity = archetypeDefaults?.emissiveIntensity ?? theme.nodeStyles[node.type]?.emissiveIntensity ?? 0.8;
    let radius = archetypeDefaults?.defaultRadius ?? theme.nodeStyles[node.type]?.radius ?? 0.6;
    let meshProfile = archetypeDefaults?.meshProfile ?? theme.nodeStyles[node.type]?.meshProfile ?? 'sphere';

    radius *= (node.semanticMass / 10) * (1 + heat * 0.3);

    const baseOpacity = 0.4 + (confidence * 0.5);
    const presenceOpacityBoost = 0.5 + (frameVisual.presence * presenceReactivity * 0.4);
    let opacity = baseOpacity * presenceOpacityBoost;

    if (isIlluminated) {
      emissiveIntensity *= 2.5;
      opacity = Math.min(1.0, opacity * 1.5);
    }
    if (isActiveCluster) {
      emissiveIntensity *= 1.3;
      opacity = Math.min(1.0, opacity * 1.2);
    }
    if (isSearchResult || isSearchMatch) {
      emissiveIntensity *= 1.8;
      opacity = Math.min(1.0, opacity * 1.3);
    }
    if (isDimmed) {
      opacity *= 0.15;
      emissiveIntensity *= 0.3;
    }

    const visualColor = isIlluminated 
      ? blendColors(baseColor, presenceGlow, 0.4)
      : isSearchMatch || isSearchResult
        ? blendColors(baseColor, '#ffff00', 0.5)
        : signatureColor
          ? blendColors(baseColor, signatureColor, 0.3)
          : baseColor;

    return {
      id: node.id,
      position: simNode.position,
      velocity: simNode.velocity,
      radius,
      color: visualColor,
      scale: 1.0 + (frameVisual.energy * 0.1) + (heat * 0.2) + (energyFlow * 0.3),
      opacity,
      meshProfile,
      emissiveIntensity,
      heat,
      confidence,
      isIlluminated,
      signature,
      type: node.type,
      archetype,
      label: node.label,
      neighborhoodId: node.neighborhoodId,
      clusterId: node.clusterId,
      presenceReactivity,
    };
  }).filter((n) => n !== null) as VisualNode[];

  const visualEdges: VisualEdge[] = graph.edges
    .map(edge => {
      const sourceSim = simNodes.find(n => n.id === edge.sourceId);
      const targetSim = simNodes.find(n => n.id === edge.targetId);
      if (!sourceSim || !targetSim) return null;

      const sourceNode = graph.nodes.find(n => n.id === edge.sourceId);
      const targetNode = graph.nodes.find(n => n.id === edge.targetId);
      
      const isIlluminated = (sourceNode && illuminatedNodeIds.has(sourceNode.id)) || 
                            (targetNode && illuminatedNodeIds.has(targetNode.id));
      const isSearchHighlighted = searchQuery && (
        (sourceNode && (sourceNode.label.toLowerCase().includes(searchQuery.toLowerCase()) || searchResults.has(sourceNode.id))) ||
        (targetNode && (targetNode.label.toLowerCase().includes(searchQuery.toLowerCase()) || searchResults.has(targetNode.id)))
      );

      const edgeFlow = (energyFlows.get(edge.id) || 0);
      const baseThickness = theme.edgeStyle.thickness * edge.semanticStrength;
      const thickness = isIlluminated ? baseThickness * 2.5 : isSearchHighlighted ? baseThickness * 2.0 : baseThickness;

      const edgeType = edge.edgeType || 'semantic';
      const baseColor = theme.edgeStyle.color;
      let color = isIlluminated 
        ? '#ffffff'
        : isSearchHighlighted
          ? '#ffff00'
          : edgeType === 'hierarchical' ? '#ffaa00'
          : edgeType === 'temporal' ? '#00ffff'
          : edgeType === 'associative' ? '#aa44ff'
          : baseColor;

      let opacity = isIlluminated ? 1.0 : isSearchHighlighted ? 0.9 : theme.edgeStyle.opacity;

      if (edgeFlow > 0) {
        opacity = Math.min(1.0, opacity + edgeFlow * 0.5);
        color = blendColors(color, presenceGlow, edgeFlow * 0.5);
      }

      return {
        id: edge.id,
        sourcePos: sourceSim.position,
        targetPos: targetSim.position,
        thickness,
        color,
        opacity,
        isIlluminated,
        energyFlow: edgeFlow,
        edgeType,
      };
    })
.filter((e) => e !== null) as VisualEdge[];

  const neighborhoods: NeighborhoodVisualState[] = NEIGHBORHOODS.map(n => {
    const nodesInHood = graph.nodes.filter(node => node.neighborhoodId === n.id);
    return {
      id: n.id,
      label: n.label,
      position: n.position,
      color: n.color,
      icon: n.icon,
      isActive: activeClusterIds.has(n.id),
      isHovered: false,
      nodeCount: nodesInHood.length,
    };
  });

  return {
    nodes: visualNodes,
    edges: visualEdges,
    activeNeighborhoodId: Array.from(activeClusterIds)[0],
    presenceState,
    cameraPivot: { x: 0, y: 0, z: 0 },
    zoomLevel: 'universe',
    neighborhoods,
  };
}

function blendColors(colorA: string, colorB: string, factor: number): string {
  const parse = (c: string) => {
    if (c.startsWith('#')) {
      const hex = c.slice(1);
      return {
        r: parseInt(hex.slice(0, 2), 16),
        g: parseInt(hex.slice(2, 4), 16),
        b: parseInt(hex.slice(4, 6), 16),
      };
    }
    if (c.startsWith('hsl')) {
      const match = c.match(/hsl\((\d+),\s*(\d+)%,\s*(\d+)%\)/);
      if (match) {
        const h = parseInt(match[1]);
        const s = parseInt(match[2]);
        const l = parseInt(match[3]);
        return hslToRgb(h, s, l);
      }
    }
    return { r: 128, g: 128, b: 128 };
  };

  const a = parse(colorA);
  const b = parse(colorB);
  const r = Math.round(a.r + (b.r - a.r) * factor);
  const g = Math.round(a.g + (b.g - a.g) * factor);
  const bl = Math.round(a.b + (b.b - a.b) * factor);
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${bl.toString(16).padStart(2, '0')}`;
}

function hslToRgb(h: number, s: number, l: number): { r: number; g: number; b: number } {
  s /= 100;
  l /= 100;
  const k = (n: number) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return {
    r: Math.round(255 * f(0)),
    g: Math.round(255 * f(8)),
    b: Math.round(255 * f(4)),
  };
}

export function createMapperContext(partial: Partial<MapperContext>): MapperContext {
  return {
    illuminatedNodeIds: new Set(),
    activeClusterIds: new Set(),
    presenceState: 'Idle',
    presenceIntensity: 0.5,
    currentTime: Date.now(),
    searchQuery: '',
    searchResults: new Set(),
    energyFlows: new Map(),
    ...partial,
  };
}