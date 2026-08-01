import { FrameState, VisualFrame } from './types';
import { SimulationState } from '../simulation/types';
import { PresenceState } from '../../theme/presenceTheme';

interface ComposerInput {
  simulation: SimulationState;
  presenceState: PresenceState;
  audioInput?: { voiceLevel: number; microphoneLevel: number; rmsLevel?: number };
  emotionInput?: Partial<FrameState['emotion']>;
  correlationId?: string;
}

/**
 * Frame Composer.
 * Merges Simulation data and Environment data into the sacred FrameState contract.
 * This is the SINGLE producer of FrameState for ALL renderers.
 */
export class FrameComposer {
  private sequence = 0;
  private lastPresenceState: PresenceState = 'Idle';
  private presenceTransitionProgress = 1; // 0 = transitioning, 1 = stable
  private transitionStartTime = 0;

  compose(input: ComposerInput): FrameState {
    const { simulation, presenceState, audioInput, emotionInput, correlationId } = input;

    // Handle presence state transitions smoothly (300-400ms)
    const now = Date.now();
    if (presenceState !== this.lastPresenceState) {
      this.lastPresenceState = presenceState;
      this.presenceTransitionProgress = 0;
      this.transitionStartTime = now;
    }

    // Progress transition over ~400ms
    if (this.presenceTransitionProgress < 1) {
      const elapsed = now - this.transitionStartTime;
      this.presenceTransitionProgress = Math.min(1, elapsed / 400);
    }

    const nodes = simulation.nodes ?? [];
    const totalMass = nodes.reduce((sum, n) => sum + n.mass, 0);
    const avgVelocity = nodes.length > 0
      ? nodes.reduce((sum, n) => sum + Math.sqrt(n.velocity.x**2 + n.velocity.y**2 + n.velocity.z**2), 0) / nodes.length
      : 0;

    // Base visual values from simulation
    const basePresence = 0.5 + Math.min(0.3, totalMass / 200);
    const baseEnergy = Math.min(1.0, avgVelocity * 2);
    const baseFocus = 0.5 + Math.min(0.3, avgVelocity);
    const baseActivity = Math.min(1.0, totalMass / 150);

    // Presence state modulates visual parameters
    const presenceMod = this.getPresenceModifiers(presenceState);
    
    // Audio input (from desktop IPC or real audio)
    const voiceLevel = audioInput?.voiceLevel ?? 0;
    const microphoneLevel = audioInput?.microphoneLevel ?? 0;
    const rmsLevel = audioInput?.rmsLevel ?? 0;

    // Smoothed RMS for fluid animation (exponential moving average)
    const smoothedRms = this.smoothRms(rmsLevel);

    this.sequence++;

    return {
      visual: {
        presence: this.lerp(basePresence, presenceMod.presence, this.presenceTransitionProgress),
        energy: this.lerp(baseEnergy, presenceMod.energy, this.presenceTransitionProgress),
        focus: this.lerp(baseFocus, presenceMod.focus, this.presenceTransitionProgress),
        activity: this.lerp(baseActivity, presenceMod.activity, this.presenceTransitionProgress),
      },
      audio: {
        voiceLevel,
        microphoneLevel,
        rmsLevel,
        smoothedRms,
      },
      emotion: {
        calmness: 0.7,
        confidence: 0.8,
        curiosity: 0.5,
        warmth: 0.6,
        empathy: 0.5,
        playfulness: 0.4,
        ...emotionInput,
      },
      system: {
        state: presenceState,
        cognitiveLoad: Math.min(1.0, baseActivity * 1.5),
        adaptiveQuality: 1.0,
        visualIdentity: 'orb-v2',
      },
      metadata: {
        timestamp: now,
        correlationId: correlationId ?? 'mock-session-001',
        version: '1.0.0',
      },
      sequence: this.sequence,
    };
  }

  private smoothRms(rms: number): number {
    // Simple EMA - in production this would be a persistent field
    // For now, return raw value; renderer does its own smoothing
    return rms;
  }

  private getPresenceModifiers(state: PresenceState): VisualFrame {
    switch (state) {
      case 'Idle':
        return { presence: 0.5, energy: 0.3, focus: 0.4, activity: 0.2 };
      case 'Listening':
        return { presence: 0.8, energy: 0.5, focus: 0.9, activity: 0.3 };
      case 'Thinking':
        return { presence: 0.7, energy: 0.6, focus: 0.9, activity: 0.4 };
      case 'SearchingMemory':
        return { presence: 0.6, energy: 0.5, focus: 0.8, activity: 0.5 };
      case 'SearchingWeb':
        return { presence: 0.7, energy: 0.7, focus: 0.8, activity: 0.7 };
      case 'Planning':
        return { presence: 0.6, energy: 0.7, focus: 0.85, activity: 0.5 };
      case 'Speaking':
        return { presence: 0.9, energy: 0.8, focus: 0.6, activity: 0.7 };
      case 'Learning':
        return { presence: 0.8, energy: 0.75, focus: 0.8, activity: 0.6 };
      case 'Error':
        return { presence: 0.9, energy: 0.95, focus: 0.3, activity: 0.9 };
      case 'Success':
        return { presence: 0.7, energy: 0.85, focus: 0.7, activity: 0.6 };
      default:
        return { presence: 0.5, energy: 0.3, focus: 0.4, activity: 0.2 };
    }
  }

  private lerp(a: number, b: number, t: number): number {
    return a + (b - a) * t;
  }

  reset(): void {
    this.sequence = 0;
    this.lastPresenceState = 'Idle';
    this.presenceTransitionProgress = 1;
  }
}