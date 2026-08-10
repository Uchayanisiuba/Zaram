// desktop/src/shared/personaVoices.ts
//
// Single source of truth for persona-to-voice mapping.
// Shared across backend, desktop, and frontend.

export const PERSONA_VOICES: Record<string, string> = {
  zaram_prime: 'af_heart',
  baba: 'am_michael',
  nova: 'af_nicole',
  mentor: 'am_adam',
  creator: 'af_bella',
  analyst: 'am_michael',
  researcher: 'af_heart',
  minimal: 'af_nicole',
} as const

export type PersonaId = keyof typeof PERSONA_VOICES

export function resolveVoice(persona: string): string {
  return PERSONA_VOICES[persona] ?? PERSONA_VOICES.zaram_prime
}

export function getPersonaVoice(persona: PersonaId): string {
  return PERSONA_VOICES[persona]
}