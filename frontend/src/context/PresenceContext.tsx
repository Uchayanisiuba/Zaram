// frontend/src/context/PresenceContext.tsx
//
// Presence Runtime Context
// Provides the unified FrameState to all embodiments (Conversation, Knowledge Universe, etc.)
// Single source of truth for Presence across the entire application.

import React, { createContext, useContext, useEffect, useState, useRef } from 'react';
import { PresenceState } from '@/theme/presenceTheme';
import { applyPresenceTheme } from '@/theme/presenceTheme';
import { FrameState, IDLE_FRAME } from '@/core/frame/types';
import { SimulationState } from '@/core/simulation/types';
import { FrameComposer } from '@/core/frame/composer';
import { desktop } from '@/desktop/desktop-bridge';

interface PresenceRuntimeState {
  frameState: FrameState;
  presenceState: PresenceState;
  setPresenceState: (state: PresenceState) => void;
  isConnected: boolean;
}

const PresenceRuntimeContext = createContext<PresenceRuntimeState | null>(null);
const FrameStateRuntimeContext = createContext<FrameState | undefined>(undefined);

interface PresenceProviderProps {
  children: React.ReactNode;
}

export function PresenceProvider({ children }: PresenceProviderProps) {
  const [frameState, setFrameState] = useState<FrameState>(IDLE_FRAME);
  const [presenceState, setPresenceState] = useState<PresenceState>('Idle');
  const [isConnected, setIsConnected] = useState(false);
  
  const frameComposerRef = useRef(new FrameComposer());
  const simulationStateRef = useRef<SimulationState>({
    nodes: [],
    timestamp: Date.now(),
  });
  const animationFrameRef = useRef<number | null>(null);

  // Initialize IPC listeners for desktop presence events
  useEffect(() => {
    let offFrame: (() => void) | undefined;
    let offState: (() => void) | undefined;
    let offHealth: (() => void) | undefined;

    // Listen for FrameState from desktop Presence Runtime (pushed at animation frequency)
    if (desktop.presence?.onFrame) {
      offFrame = desktop.presence.onFrame((data: any) => {
        const ipcFrameState = data as FrameState;
        setFrameState(ipcFrameState);
      });
    }

    // Listen for Presence State changes
    if (desktop.presence?.onState) {
      offState = desktop.presence.onState((data: any) => {
        if (data?.state) {
          setPresenceState(data.state);
        }
      });
    }

    // Listen for health/connection status
    if (desktop.presence?.onHealth) {
      offHealth = desktop.presence.onHealth((data: any) => {
        setIsConnected(data?.healthy ?? false);
      });
    }

    return () => {
      offFrame?.();
      offState?.();
      offHealth?.();
    };
  }, []);

  // Bridge presence state to CSS theme variables so all spatial UI
  // (glass glow, orb color, selection rings) stays synchronized.
  useEffect(() => {
    if (typeof document !== 'undefined') {
      applyPresenceTheme(document.documentElement, presenceState)
    }
  }, [presenceState])

  // Local animation loop for composing FrameState when no desktop IPC is available
  // (e.g., in browser mode or during development)
  // NOTE: frameState updates every frame but lives in a separate context so
  // presence-only consumers (glass, HUD) don't re-render at 60fps.
  useEffect(() => {
    let mounted = true;

    const tick = (_time: number) => {
      if (!mounted) return;
      
      const composedFrame = frameComposerRef.current.compose({
        simulation: simulationStateRef.current,
        presenceState,
        audioInput: { voiceLevel: 0, microphoneLevel: 0, rmsLevel: 0 },
        correlationId: 'presence-runtime',
      });

      setFrameState(composedFrame);
      animationFrameRef.current = requestAnimationFrame(tick);
    };

    animationFrameRef.current = requestAnimationFrame(tick);
    return () => {
      mounted = false;
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [presenceState]);

  const presenceValue: PresenceRuntimeState = {
    frameState,
    presenceState,
    setPresenceState,
    isConnected,
  };

  return (
    <PresenceRuntimeContext.Provider value={presenceValue}>
      <FrameStateRuntimeContext.Provider value={frameState}>
        {children}
      </FrameStateRuntimeContext.Provider>
    </PresenceRuntimeContext.Provider>
  );
}

export function usePresenceRuntime(): PresenceRuntimeState {
  const context = useContext(PresenceRuntimeContext);
  if (!context) {
    throw new Error('usePresenceRuntime must be used within a PresenceProvider');
  }
  return context;
}

// Helper hook for components that just need the current FrameState
// Reads from the high-frequency FrameState context so presence-only consumers
export function useFrameState(): FrameState {
  const frameState = useContext(FrameStateRuntimeContext);
  if (frameState === undefined) {
    throw new Error('useFrameState must be used within a PresenceProvider');
  }
  return frameState;
}

// Helper hook for components that just need the current PresenceState
export function usePresenceState(): PresenceState {
  const { presenceState } = usePresenceRuntime();
  return presenceState;
}