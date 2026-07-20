export interface RuntimeState {
  state: 'Idle' | 'Listening' | 'Thinking' | 'Speaking' | 'Working' | 'Sleeping' | 'Error';
  cognitiveLoad?: number;
  correlationId?: string;
  audio?: {
    voiceLevel?: number;
    microphoneLevel?: number;
  };
}
