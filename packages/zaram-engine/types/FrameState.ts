export interface FrameState {
  visual: {
    presence: number; // 0.0 - 1.0
    energy: number;   // 0.0 - 1.0
    focus: number;    // 0.0 - 1.0
    activity: number; // 0.0 - 1.0
  };
  audio: {
    voiceLevel: number;      // 0.0 - 1.0
    microphoneLevel: number; // 0.0 - 1.0
  };
  emotion: {
    calmness: number;
    confidence: number;
    curiosity: number;
    warmth: number;
    empathy: number;
    playfulness: number;
  };
  system: {
    state: 'Idle' | 'Listening' | 'Thinking' | 'Speaking' | 'Working' | 'Sleeping' | 'Error';
    cognitiveLoad: number;
    visualIdentity: number; // Persistent signature seed
  };
  metadata: {
    timestamp: number;
    correlationId: string;
    version: string;
  };
}