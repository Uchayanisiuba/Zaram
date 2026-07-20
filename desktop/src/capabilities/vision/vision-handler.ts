// desktop/src/capabilities/vision/vision-handler.ts
//
// Milestone 2.1 — Vision ExecutionHandler implementations.
//
// Each handler receives an ExecutionRequest, validates input, delegates to
// the backend vision endpoint, and reports progress through controls.

import type { ExecutionRequest, ExecutionContext, ExecutionControls, ExecutionHandler } from '../../runtime/execution'
import type { VisionHandlerContext } from './vision-types'

export function createVisionHandlers(emit: (eventType: string, data: Record<string, unknown>) => void, recordOperation: (capabilityId: string) => void): VisionHandlerContext {
  return { emit, recordOperation }
}

async function streamVisionResponse(prompt: string, image: string): Promise<string> {
  const postData = JSON.stringify({ prompt, image })
  
  return new Promise((resolve, reject) => {
      const req = require('http').request({
        hostname: '127.0.0.1',
        port: 8000,
        path: '/vision/analyze',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(postData)
        }
      }, (res: any) => {
      if (res.statusCode !== 200) {
        reject(new Error(`Vision API failed: ${res.statusCode}`))
        return
      }

      const decoder = new TextDecoder()
      let fullText = ''
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
            resolve(fullText)
            return
          }
          try {
            const event = JSON.parse(data)
            if (event.type === 'token') {
              fullText += event.content || ''
            } else if (event.type === 'error') {
              reject(new Error(event.content || 'Vision backend error'))
              return
            }
          } catch {
            // ignore malformed events
          }
        }
      })

      res.on('end', () => {
        resolve(fullText)
      })
    })

      req.on('error', (error: any) => {
        reject(error)
      })

    req.setTimeout(120000, () => {
      req.destroy()
      reject(new Error('Vision request timeout'))
    })

    req.write(postData)
    req.end()
  })
}

export function handleAnalyze(ctx: VisionHandlerContext): ExecutionHandler {
  return async (req: ExecutionRequest, _context: ExecutionContext, controls: ExecutionControls) => {
    const prompt = typeof req.input === 'string' ? req.input : (req.input as any)?.prompt || 'Describe this image'
    const image = typeof req.input === 'object' && req.input !== null ? (req.input as any).image : ''
    
    if (!image) {
      controls.fail({ code: 'validation_error', message: 'image is required', attempt: 0, kind: 'handler' })
      return
    }

    controls.reportProgress(0.1)
    ctx.recordOperation('vision.analyze')
    
    try {
      const response = await streamVisionResponse(prompt, image)
      controls.reportProgress(1.0)
      controls.succeed({ response })
    } catch (error) {
      controls.fail({ code: 'handler', message: String(error), attempt: 0, kind: 'handler' })
    }
  }
}

export function handleScreen(ctx: VisionHandlerContext): ExecutionHandler {
  return async (req: ExecutionRequest, _context: ExecutionContext, controls: ExecutionControls) => {
    const prompt = typeof req.input === 'string' ? req.input : (req.input as any)?.prompt || 'Describe this screen'
    const image = typeof req.input === 'object' && req.input !== null ? (req.input as any).image : ''
    
    if (!image) {
      controls.fail({ code: 'validation_error', message: 'image is required for screen capture', attempt: 0, kind: 'handler' })
      return
    }

    controls.reportProgress(0.1)
    ctx.recordOperation('vision.screen')
    
    try {
      const response = await streamVisionResponse(`${prompt} (screen capture)`, image)
      controls.reportProgress(1.0)
      controls.succeed({ response })
    } catch (error) {
      controls.fail({ code: 'handler', message: String(error), attempt: 0, kind: 'handler' })
    }
  }
}

export function handleCamera(ctx: VisionHandlerContext): ExecutionHandler {
  return async (req: ExecutionRequest, _context: ExecutionContext, controls: ExecutionControls) => {
    const prompt = typeof req.input === 'string' ? req.input : (req.input as any)?.prompt || 'Describe this image'
    const image = typeof req.input === 'object' && req.input !== null ? (req.input as any).image : ''
    
    if (!image) {
      controls.fail({ code: 'validation_error', message: 'image is required for camera capture', attempt: 0, kind: 'handler' })
      return
    }

    controls.reportProgress(0.1)
    ctx.recordOperation('vision.camera')
    
    try {
      const response = await streamVisionResponse(`${prompt} (camera capture)`, image)
      controls.reportProgress(1.0)
      controls.succeed({ response })
    } catch (error) {
      controls.fail({ code: 'handler', message: String(error), attempt: 0, kind: 'handler' })
    }
  }
}

export function handleDocument(ctx: VisionHandlerContext): ExecutionHandler {
  return async (req: ExecutionRequest, _context: ExecutionContext, controls: ExecutionControls) => {
    const prompt = typeof req.input === 'string' ? req.input : (req.input as any)?.prompt || 'Extract text from this document'
    const image = typeof req.input === 'object' && req.input !== null ? (req.input as any).image : ''
    
    if (!image) {
      controls.fail({ code: 'validation_error', message: 'image is required for document analysis', attempt: 0, kind: 'handler' })
      return
    }

    controls.reportProgress(0.1)
    ctx.recordOperation('vision.document')
    
    try {
      const response = await streamVisionResponse(`${prompt} (document)`, image)
      controls.reportProgress(1.0)
      controls.succeed({ response })
    } catch (error) {
      controls.fail({ code: 'handler', message: String(error), attempt: 0, kind: 'handler' })
    }
  }
}

export function handleOCR(ctx: VisionHandlerContext): ExecutionHandler {
  return async (req: ExecutionRequest, _context: ExecutionContext, controls: ExecutionControls) => {
    const prompt = typeof req.input === 'string' ? req.input : (req.input as any)?.prompt || 'Extract all text from this image'
    const image = typeof req.input === 'object' && req.input !== null ? (req.input as any).image : ''
    
    if (!image) {
      controls.fail({ code: 'validation_error', message: 'image is required for OCR', attempt: 0, kind: 'handler' })
      return
    }

    controls.reportProgress(0.1)
    ctx.recordOperation('vision.ocr')
    
    try {
      const response = await streamVisionResponse(`${prompt} (OCR)`, image)
      controls.reportProgress(1.0)
      controls.succeed({ response })
    } catch (error) {
      controls.fail({ code: 'handler', message: String(error), attempt: 0, kind: 'handler' })
    }
  }
}
