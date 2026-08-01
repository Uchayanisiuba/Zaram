import { useEffect, useRef } from 'react';
import { useFrameStore } from '@/stores/frameStore';
import { SimulationRuntime } from '@/core/simulation/runtime';
import { FrameComposer } from '@/core/frame/composer';
import { SimulationState, SimulationNode } from '@/core/simulation/types';
import { SpatialGraph } from '@/core/semantic/types';
import { PresenceState } from '@/theme/presenceTheme';

const MOCK_INITIAL_NODES: SimulationNode[] = [
  { id: 'node-1', mass: 10, position: { x: 0, y: 0, z: 0 }, velocity: { x: 0, y: 0, z: 0 }, acceleration: { x: 0, y: 0, z: 0 } },
  { id: 'node-2', mass: 20, position: { x: 50, y: 50, z: 0 }, velocity: { x: 0, y: 0, z: 0 }, acceleration: { x: 0, y: 0, z: 0 } },
];

const MOCK_INITIAL_STATE: SimulationState = {
  nodes: MOCK_INITIAL_NODES,
  timestamp: Date.now(),
};

const MOCK_SPATIAL_GRAPH: SpatialGraph = {
  nodes: [{ id: 'node-1', type: 'concept', label: 'Hello', semanticMass: 1 }, { id: 'node-2', type: 'concept', label: 'World', semanticMass: 1 }],
  edges: [{ id: 'edge-1', sourceId: 'node-1', targetId: 'node-2', semanticStrength: 1.0 }],
};

const PRESENCE_CYCLE: PresenceState[] = ['Idle', 'Listening', 'Thinking', 'Speaking'];

export function useRuntimeLoop(fps: number = 60) {
  const runtimeRef = useRef<SimulationRuntime | null>(null);
  const composerRef = useRef<FrameComposer | null>(null);
  const frameRef = useRef<number>(0);
  const updateFrame = useFrameStore((s) => s.updateFrame);
  const presenceIndexRef = useRef(0);

  useEffect(() => {
    // Initialize the core engine
    runtimeRef.current = new SimulationRuntime(MOCK_INITIAL_STATE);
    composerRef.current = new FrameComposer();

    const interval = 1000 / fps;
    let lastTime = performance.now();

    // Cycle through presence states for demonstration
    const presenceTimer = setInterval(() => {
      presenceIndexRef.current = (presenceIndexRef.current + 1) % PRESENCE_CYCLE.length;
    }, 3000);

    const loop = (currentTime: number) => {
      const delta = currentTime - lastTime;
      
      if (delta >= interval) {
        lastTime = currentTime - (delta % interval);
        
        // Tick the simulation
        const simState = runtimeRef.current!.tick(MOCK_SPATIAL_GRAPH, delta / 1000); // deltaTime in seconds
        
        // Compose the frame
        const frameState = composerRef.current!.compose({
          simulation: simState,
          presenceState: PRESENCE_CYCLE[presenceIndexRef.current],
        });
        
        // Push to React world
        updateFrame(frameState);
      }
      
      frameRef.current = requestAnimationFrame(loop);
    };

    frameRef.current = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(frameRef.current);
      clearInterval(presenceTimer);
    };
  }, [fps, updateFrame]);
}