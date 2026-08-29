// desktop/src/runtime/voice/voice-runtime.ts
//
// Voice Runtime: Owns speech synthesis lifecycle.
// Subscribes to executive.speak events, calls speech capability,
// and publishes voice.* events for other subsystems.
// Nothing calls VoiceRuntime directly — everything communicates via events.

import { eventBus, type ZaramEventType } from '../event-bus'
import type { IExecutionRuntime } from '../execution'
import type { ExecutiveRuntime } from '../executive'
import { resolveVoice } from '../../shared/personaVoices'

export interface VoiceRuntimeOptions {
  executionRuntime?: IExecutionRuntime
  executiveRuntime?: ExecutiveRuntime
  persona?: string
}

type SpeechEventCallback = (event: { type: string; data: Record<string, unknown> }) => void

export class VoiceRuntime {
  private executionRuntime?: IExecutionRuntime
  private executiveRuntime?: ExecutiveRuntime
  private persona: string = 'zaram_prime'
  private currentAudioId: string | null = null
  private currentSequence = 0
  private subscribers = new Set<SpeechEventCallback>()
  private unsubExecutiveSpeak: (() => void) | null = null
  private unsubExecutivePause: (() => void) | null = null
  private unsubExecutiveStop: (() => void) | null = null
  private unsubVoiceChunk: (() => void) | null = null
  private unsubVoiceLevel: (() => void) | null = null
  private unsubExecutionEvents: (() => void) | null = null
  private isSpeaking = false

  constructor(options: VoiceRuntimeOptions = {}) {
    this.executionRuntime = options.executionRuntime
    this.executiveRuntime = options.executiveRuntime
    this.persona = options.persona ?? 'zaram_prime'

    // Subscribe to executive.speak events
    this.unsubExecutiveSpeak = eventBus.subscribe('executive:speak' as ZaramEventType, (event) => {
      const data = event.data as { text: string; persona?: string; voice?: string }
      this.handleSpeakRequest(data.text, data.persona ?? this.persona, data.voice)
    })

    // Subscribe to executive:pause_speech
    this.unsubExecutivePause = eventBus.subscribe('executive:pause_speech' as ZaramEventType, (event) => {
      const data = event.data as { request_id?: string }
      this.handlePauseRequest(data.request_id)
    })

    // Subscribe to executive:stop_speech
    this.unsubExecutiveStop = eventBus.subscribe('executive:stop_speech' as ZaramEventType, (event) => {
      const data = event.data as { request_id?: string }
      this.handleStopRequest(data.request_id)
    })

    // Subscribe to voice.chunk and voice.level from backend for orb visualization
    this.unsubVoiceChunk = eventBus.subscribe('voice:chunk' as ZaramEventType, (event) => {
      const data = event.data as { rmsLevel?: number; audioId?: string }
      if (data.rmsLevel !== undefined && this.currentAudioId) {
        this.publish('voice:chunk', {
          audioId: this.currentAudioId,
          sequence: this.currentSequence,
          chunk: new Uint8Array(), // placeholder, backend sends actual audio
          rmsLevel: data.rmsLevel,
          timestamp: Date.now(),
        })
      }
    })

    this.unsubVoiceLevel = eventBus.subscribe('voice:level' as ZaramEventType, (event) => {
      const data = event.data as { level?: number; request_id?: string }
      if (data.level !== undefined) {
        this.publish('voice:level', {
          audioId: this.currentAudioId,
          level: data.level,
          timestamp: Date.now(),
        })
      }
    })

    // Subscribe to execution events to track audio chunks
    this.unsubExecutionEvents = this.executionRuntime?.subscribe((event) => {
      this.handleExecutionEvent(event)
    }) ?? null
  }

  setPersona(persona: string): void {
    this.persona = persona
  }

  subscribe(callback: SpeechEventCallback): () => void {
    this.subscribers.add(callback)
    return () => this.subscribers.delete(callback)
  }

  private handleSpeakRequest(text: string, persona: string, voice?: string): void {
    if (!text || !text.trim()) return
    if (!this.executionRuntime) {
      console.warn('[VoiceRuntime] No execution runtime available for speech synthesis')
      return
    }

    this.currentAudioId = `audio_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
    this.currentSequence = 0
    this.isSpeaking = true

    const resolvedVoice = voice || this.resolveVoice(persona)

    this.publish('voice:started', {
      audioId: this.currentAudioId,
      text,
      persona,
      voice: resolvedVoice,
      sequence: this.currentSequence,
    })

    // **`speech.tts` has had no handler since 28 August 2026, and this call
    // is the last thing still reaching for it.** The handler posted to
    // `/voice/stream` on 8420 with no `X-Zaram-Auth`, so it had returned 401
    // since the per-launch secret shipped; it was removed with the Knowledge
    // and Vision packs for the same reason.
    //
    // This is not the path that speaks. `docs/SPEECH.md` is the authority and
    // it puts synthesis in the renderer: `chatStore.sendMessage` reads the
    // embodiment renderer at send, and `speechStore` calls
    // `POST /voice/synthesize`. Nothing in that chain passes through here.
    //
    // Left in place rather than deleted because removing it takes
    // `VoiceRuntime` (full) with it, and that is a wider question than the
    // audit that found this: whether the desktop execution pipeline keeps a
    // backend-facing half at all, given `executeCapability` has no caller in
    // the live frontend. Decide that, then delete this.
    this.executionRuntime.execute({
      capabilityId: 'speech.tts',
      input: { text, persona, voice: resolvedVoice },
      context: {
        correlationId: this.currentAudioId,
        grantedPermissions: [],
        createdAt: Date.now(),
      },
      options: { tag: 'speech' },
    })
  }

  private handlePauseRequest(requestId?: string): void {
    if (!this.currentAudioId) return
    // For now, emit pause event; backend handles pause via speech capability
    this.publish('voice:paused', {
      audioId: this.currentAudioId,
      requestId,
    })
    // Future: call executionRuntime.cancel or a pause capability
  }

  private handleStopRequest(requestId?: string): void {
    if (!this.currentAudioId) return
    this.isSpeaking = false
    this.publish('voice:failed', {
      audioId: this.currentAudioId,
      error: 'Speech stopped by executive',
      requestId,
    })
    this.currentAudioId = null
    // Future: call executionRuntime.cancel
  }

  private handleExecutionEvent(event: any): void {
    const eventType = event?.event_type
    const data = event?.data

    if (!data || data.capabilityId !== 'speech.tts') return

    switch (eventType) {
      case 'execution.audio_chunk': {
        this.currentSequence++
        const chunk = data as any
        this.publish('voice:chunk', {
          audioId: this.currentAudioId,
          sequence: this.currentSequence,
          chunk: chunk.chunk,
          rmsLevel: chunk.rmsLevel,
          timestamp: Date.now(),
        })
        break
      }
      case 'execution.completed': {
        if (this.isSpeaking) {
          this.isSpeaking = false
          this.publish('voice.finished', {
            audioId: this.currentAudioId,
            text: data.output?.response || '',
            durationMs: data.durationMs,
          })
          this.currentAudioId = null
        }
        break
      }
      case 'execution.failed': {
        if (this.isSpeaking) {
          this.isSpeaking = false
          this.publish('voice:failed', {
            audioId: this.currentAudioId,
            error: data.error?.message || 'Speech synthesis failed',
          })
          this.currentAudioId = null
        }
        break
      }
      case 'execution.cancelled': {
        if (this.isSpeaking) {
          this.isSpeaking = false
          this.publish('voice:failed', {
            audioId: this.currentAudioId,
            error: 'Speech synthesis cancelled',
          })
          this.currentAudioId = null
        }
        break
      }
    }
  }

  private resolveVoice(persona: string): string {
    return resolveVoice(persona)
  }

  private publish(eventType: string, data: Record<string, unknown>): void {
    const event = { type: eventType, data }
    this.subscribers.forEach((cb) => {
      try {
        cb(event)
      } catch (err) {
        console.error('[VoiceRuntime] Subscriber error:', err)
      }
    })

    // Also publish to global event bus for other runtimes
    eventBus.publish(eventType as ZaramEventType, data, 'voice', this.currentAudioId ?? undefined)
  }

  isActive(): boolean {
    return this.isSpeaking
  }

  getCurrentAudioId(): string | null {
    return this.currentAudioId
  }

  shutdown(): void {
    this.unsubExecutiveSpeak?.()
    this.unsubExecutivePause?.()
    this.unsubExecutiveStop?.()
    this.unsubVoiceChunk?.()
    this.unsubVoiceLevel?.()
    this.unsubExecutionEvents?.()
    this.subscribers.clear()
    this.executionRuntime = undefined
    this.executiveRuntime = undefined
  }
}

export type { SpeechEventCallback }