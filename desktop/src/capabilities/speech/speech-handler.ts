// desktop/src/capabilities/speech/speech-handler.ts
//
// Speech TTS ExecutionHandler implementations.
// Calls the backend /voice/stream endpoint and streams audio chunks via
// ExecutionControls.reportAudioChunk.

import type { ExecutionRequest, ExecutionContext, ExecutionControls, ExecutionHandler } from '../../runtime/execution'
import { resolveVoice } from '../../shared/personaVoices'

export interface SpeechHandlerContext {
  backendUrl: string
  emit: (eventType: string, data: Record<string, unknown>) => void
  recordOperation: (capabilityId: string) => void
}

export function createSpeechHandlers(backendUrl: string): SpeechHandlerContext {
  return {
    backendUrl,
    emit: () => {},
    recordOperation: () => {}
  }
}

async function streamVoiceSynthesis(
  backendUrl: string,
  text: string,
  voice: string,
  onChunk: (chunk: any) => void
): Promise<void> {
  const postData = JSON.stringify({ text, voice })
  
  return new Promise((resolve, reject) => {
    const req = require('http').request({
      hostname: '127.0.0.1',
      port: 8000,
      path: '/voice/stream',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData)
      }
    }, (res: any) => {
      if (res.statusCode !== 200) {
        reject(new Error(`Voice API failed: ${res.statusCode}`))
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      res.on('data', (chunk: Buffer) => {
        buffer += decoder.decode(chunk, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        
        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed || !trimmed.startsWith('data: ')) continue
          const data = trimmed.slice(6)
          if (data === '[DONE]') {
            resolve()
            return
          }
          try {
            const event = JSON.parse(data)
            if (event.type === 'audio') {
              onChunk(event)
            } else if (event.type === 'error') {
              reject(new Error(event.content || 'Voice backend error'))
              return
            }
          } catch {
            // ignore malformed events
          }
        }
      })

      res.on('end', () => {
        resolve()
      })
    })

    req.on('error', (error: any) => {
      reject(error)
    })

    req.setTimeout(120000, () => {
      req.destroy()
      reject(new Error('Voice request timeout'))
    })

    req.write(postData)
    req.end()
  })
}

export function handleSpeechTTS(ctx: SpeechHandlerContext): ExecutionHandler {
  return async (req: ExecutionRequest, _context: ExecutionContext, controls: ExecutionControls) => {
    const text = typeof req.input === 'string' ? req.input : (req.input as any)?.text || ''
    const voice = typeof req.input === 'object' && req.input !== null ? (req.input as any).voice : ''
    const persona = typeof req.input === 'object' && req.input !== null ? (req.input as any).persona : 'zaram_prime'
    
    if (!text) {
      controls.fail({ code: 'validation_error', message: 'text is required', attempt: 0, kind: 'handler' })
      return
    }

    // Resolve voice from persona if not provided
    const resolvedVoice = voice || resolveVoice(persona)

    controls.reportProgress(0.1)
    ctx.recordOperation('speech.tts')
    
    try {
      await streamVoiceSynthesis(ctx.backendUrl, text, resolvedVoice, (audioEvent: any) => {
        controls.reportAudioChunk(audioEvent)
      })
      controls.reportProgress(1.0)
      controls.succeed({ response: 'Speech synthesis complete' })
    } catch (error) {
      controls.fail({ code: 'handler', message: String(error), attempt: 0, kind: 'handler' })
    }
  }
}