// desktop/src/capabilities/speech/speech-capability.ts
//
// Speech TTS capability descriptor for the Capability Runtime.

import type { CapabilityDescriptor, CapabilitySchema } from '../../runtime/capability'

const speechInputSchema: CapabilitySchema = {
  type: 'object',
  properties: {
    text: { type: 'string', description: 'Text to synthesize' },
    voice: { type: 'string', description: 'Voice ID (optional, defaults to persona voice)' },
    persona: { type: 'string', description: 'Persona ID for voice selection' }
  },
  required: ['text']
}

const speechOutputSchema: CapabilitySchema = {
  type: 'object',
  properties: {
    response: { type: 'string' }
  }
}

export const SPEECH_TTS_CAPABILITY: CapabilityDescriptor = {
  id: 'speech.tts',
  name: 'Speech Synthesis',
  description: 'Synthesize speech from text using the backend voice provider (Kokoro TTS)',
  category: 'speech',
  permissions: [],
  inputSchema: speechInputSchema,
  outputSchema: speechOutputSchema,
  availability: 'available',
  latencyEstimateMs: 1000,
  location: 'cloud',
  cost: 0,
  enabled: true,
  source: 'backend',
  tags: ['tts', 'voice', 'audio'],
  revision: 1,
  updatedAt: Date.now()
}

export const SPEECH_CAPABILITIES = [SPEECH_TTS_CAPABILITY]