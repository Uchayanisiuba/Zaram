// frontend/src/components/conversation/ResizablePanels.tsx
//
// Reusable resizable panel container with independent dividers.
// Each divider controls only its adjacent panels.

import { useState, useCallback, useEffect, useRef } from 'react'

interface PanelSizes {
  sidebar: number
  canvas: number
  conversation: number
}

interface ResizablePanelsProps {
  children: [React.ReactNode, React.ReactNode, React.ReactNode]
  defaultSizes?: Partial<PanelSizes>
  minWidths?: { sidebar: number; canvas: number; conversation: number }
}

const STORAGE_KEY = 'zaram-panel-sizes'

function loadSizes(defaultSizes: Partial<PanelSizes> | undefined, containerWidth: number): PanelSizes {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored) as PanelSizes
      const total = parsed.sidebar + parsed.canvas + parsed.conversation
      if (total > 0 && total <= 100) {
        return parsed
      }
    }
  } catch {
    // ignore
  }
  return {
    sidebar: defaultSizes?.sidebar ?? 15,
    canvas: defaultSizes?.canvas ?? 55,
    conversation: defaultSizes?.conversation ?? 30,
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

export function ResizablePanels({ children, defaultSizes, minWidths }: ResizablePanelsProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(0)
  const [sizes, setSizes] = useState<PanelSizes>(() => loadSizes(defaultSizes, 0))
  const [activeDivider, setActiveDivider] = useState<'sidebar' | 'canvas' | null>(null)

  const minSidebar = minWidths?.sidebar ?? 220
  const minCanvas = minWidths?.canvas ?? 500
  const minConversation = minWidths?.conversation ?? 350

  const toPercent = useCallback((px: number) => {
    if (!containerWidth) return 0
    return (px / containerWidth) * 100
  }, [containerWidth])

  const toPixels = useCallback((percent: number) => {
    return (percent / 100) * containerWidth
  }, [containerWidth])

  const saveSizes = useCallback((newSizes: PanelSizes) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newSizes))
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const updateWidth = () => {
      setContainerWidth(container.getBoundingClientRect().width)
    }

    updateWidth()
    const resizeObserver = new ResizeObserver(updateWidth)
    resizeObserver.observe(container)

    return () => {
      resizeObserver.disconnect()
    }
  }, [])

  useEffect(() => {
    if (!containerWidth) return

    const minSidebarPx = toPercent(minSidebar)
    const minCanvasPx = toPercent(minCanvas)
    const minConversationPx = toPercent(minConversation)
    const maxSidebarPx = 100 - minCanvasPx - minConversationPx
    const maxCanvasPx = 100 - minSidebarPx - minConversationPx

    setSizes(prev => ({
      sidebar: clamp(prev.sidebar, minSidebarPx, maxSidebarPx),
      canvas: clamp(prev.canvas, minCanvasPx, maxCanvasPx),
      conversation: clamp(prev.conversation, minConversationPx, 100 - minSidebarPx - minCanvasPx),
    }))
  }, [containerWidth, minSidebar, minCanvas, minConversation, toPercent])

  useEffect(() => {
    if (!activeDivider) return

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const mouseX = e.clientX - rect.left

      setSizes(prev => {
        const minSidebarPx = toPercent(minSidebar)
        const minCanvasPx = toPercent(minCanvas)
        const minConversationPx = toPercent(minConversation)
        const maxSidebarPx = 100 - minCanvasPx - minConversationPx
        const maxCanvasPx = 100 - minSidebarPx - minConversationPx

        if (activeDivider === 'sidebar') {
          const newSidebar = clamp(toPercent(mouseX), minSidebarPx, maxSidebarPx)
          const newCanvas = prev.canvas
          const newConversation = 100 - newSidebar - newCanvas
          const result = {
            sidebar: newSidebar,
            canvas: newCanvas,
            conversation: Math.max(newConversation, minConversationPx),
          }
          saveSizes(result)
          return result
        } else if (activeDivider === 'canvas') {
          const sidebarPx = toPixels(prev.sidebar)
          const newCanvasPx = clamp(mouseX - sidebarPx, minCanvas, containerWidth - minSidebar - minConversation)
          const newCanvas = toPercent(newCanvasPx)
          const newConversation = 100 - prev.sidebar - newCanvas
          const result = {
            sidebar: prev.sidebar,
            canvas: Math.max(newCanvas, minCanvasPx),
            conversation: Math.max(newConversation, minConversationPx),
          }
          saveSizes(result)
          return result
        }

        return prev
      })
    }

    const handleMouseUp = () => {
      setActiveDivider(null)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [activeDivider, containerWidth, minSidebar, minCanvas, minConversation, toPercent, toPixels, saveSizes])

  const [sidebar, canvas, conversation] = children

  return (
    <div ref={containerRef} className="flex h-full w-full">
      <div style={{ width: `${sizes.sidebar}%` }} className="flex-shrink-0 h-full overflow-hidden">
        {sidebar}
      </div>
      
      <div
        onMouseDown={() => setActiveDivider('sidebar')}
        className={`w-1.5 cursor-col-resize hover:bg-cyan-500/40 transition-colors flex-shrink-0 ${activeDivider === 'sidebar' ? 'bg-cyan-500/60' : 'bg-white/5'}`}
      />
      
      <div style={{ width: `${sizes.canvas}%` }} className="flex-shrink-0 h-full overflow-visible">
        {canvas}
      </div>
      
      <div
        onMouseDown={() => setActiveDivider('canvas')}
        className={`w-1.5 cursor-col-resize hover:bg-cyan-500/40 transition-colors flex-shrink-0 ${activeDivider === 'canvas' ? 'bg-cyan-500/60' : 'bg-white/5'}`}
      />
      
      <div style={{ width: `${sizes.conversation}%` }} className="flex-shrink-0 h-full overflow-hidden">
        {conversation}
      </div>
    </div>
  )
}
