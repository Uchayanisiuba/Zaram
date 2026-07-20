import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { ConversationPanel } from '@/pages/ConversationPanel'
import { AuditTerminal } from '@/pages/AuditTerminal'
import { RuntimeInspector } from '@/pages/RuntimeInspector'
import { CapabilityExplorer } from '@/pages/CapabilityExplorer'
import { FilesystemDemo } from '@/pages/FilesystemDemo'
import { useWorkspaceContextStore } from '@/stores/workspaceContextStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'

vi.mock('@/desktop/desktop-bridge', () => ({
  desktop: {
    isDesktop: false,
    executive: {
      onSnapshot: () => () => {},
      plan: () => Promise.resolve({ steps: [] }),
      getConfidence: () => Promise.resolve(0),
      getEvidence: () => Promise.resolve([]),
      getPlan: () => Promise.resolve(null),
      getSnapshot: () => Promise.resolve(null),
    },
    execution: {
      getHistory: () => Promise.resolve([]),
      getExecution: () => Promise.resolve({ status: 'completed', output: null }),
      execute: () => Promise.resolve({ id: 'exec-1' }),
      onEvent: () => () => {},
    },
    workspace: {
      getState: () => Promise.resolve({}),
      getContext: () => Promise.resolve({}),
      getSnapshot: () => Promise.resolve(null),
      onEvent: () => () => {},
    },
    vscode: {
      getSnapshot: () => Promise.resolve({ connected: false }),
      onEvent: () => () => {},
    },
    filesystem: {
      getMetrics: () => Promise.resolve({}),
    },
    capability: {
      getSnapshot: () => Promise.resolve({ capabilities: [] }),
      onEvent: () => () => {},
    },
    backend: {
      onStatus: () => () => {},
    },
    presence: {
      getHealth: () => Promise.resolve({
        presenceRuntimeStatus: 'running',
        animationRuntimeStatus: 'running',
        embodimentHealthy: true,
        rendererHealth: 'healthy',
        uptimeMs: 1000,
      }),
    },
    dialog: {
      showOpen: () => Promise.resolve([]),
    },
    clipboard: {
      writeText: () => Promise.resolve(),
    },
    shell: {
      showItemInFolder: () => Promise.resolve(),
    },
  },
  isDesktop: false,
}))

beforeEach(async () => {
  vi.clearAllMocks()
  useWorkspaceContextStore.setState({
    snapshot: null,
    events: [],
    advancedMode: false,
    indexing: false,
    hasWorkspace: false,
  })
  useWorkspaceStore.setState({
    layout: { panels: [], splitDirection: 'horizontal' },
    activePanelId: 'conversation',
    openArtifacts: [],
  })
  localStorage.clear()
})

describe('ConversationPanel', () => {
  it('renders empty state when no messages', () => {
    render(<ConversationPanel />)
    expect(screen.getByText('How can I help you today?')).toBeTruthy()
  })

  it('shows workspace context pill when snapshot exists', async () => {
    useWorkspaceContextStore.setState({
      snapshot: {
        workspace: 'Zaram',
        framework: 'React',
        language: 'TypeScript',
        projects: 3,
        confidence: 97,
        open_modules: ['package.json'],
      },
    })
    render(<ConversationPanel />)
    expect(screen.getByText(/React/)).toBeTruthy()
    expect(screen.getByText(/TypeScript/)).toBeTruthy()
  })

  it('has an input field and send button', () => {
    render(<ConversationPanel />)
    expect(screen.getByPlaceholderText('Message Zaram...')).toBeTruthy()
  })
})

describe('AuditTerminal', () => {
  it('renders empty state when no executions', () => {
    render(<AuditTerminal />)
    expect(screen.getByText('No executions yet')).toBeTruthy()
  })

  it('shows tabs for timeline, workspace, and vscode', () => {
    render(<AuditTerminal />)
    expect(screen.getByText('Timeline')).toBeTruthy()
    expect(screen.getByText('Workspace')).toBeTruthy()
    expect(screen.getByText('VS Code')).toBeTruthy()
  })

  it('switches to workspace tab on click', async () => {
    render(<AuditTerminal />)
    fireEvent.click(screen.getByText('Workspace'))
    await waitFor(() => {
      expect(screen.getByText('Waiting for workspace events...')).toBeTruthy()
    })
  })
})

describe('RuntimeInspector', () => {
  it('renders runtime cards', async () => {
    render(<RuntimeInspector />)
    await waitFor(() => {
      expect(screen.getByText('RUNTIME INSPECTOR')).toBeTruthy()
    })
    expect(screen.getByText('Executive Runtime')).toBeTruthy()
  })

  it('shows advanced mode toggle', async () => {
    render(<RuntimeInspector />)
    expect(screen.getByText('Advanced Mode')).toBeTruthy()
  })
})

describe('CapabilityExplorer', () => {
  it('renders search input and categories', () => {
    render(<CapabilityExplorer />)
    expect(screen.getByPlaceholderText('Search capabilities...')).toBeTruthy()
    expect(screen.getByText('All')).toBeTruthy()
  })

  it('renders empty state when no capabilities', async () => {
    render(<CapabilityExplorer />)
    await waitFor(() => {
      expect(screen.getByText('No capabilities found')).toBeTruthy()
    })
  })
})

describe('FilesystemDemo', () => {
  it('renders explorer with search input', async () => {
    render(<FilesystemDemo />)
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search files...')).toBeTruthy()
    })
  })

  it('shows empty preview when no file selected', async () => {
    render(<FilesystemDemo />)
    await waitFor(() => {
      expect(screen.getByText('Select a file to preview')).toBeTruthy()
    })
  })
})

describe('workspaceStore', () => {
  it('persists layout to localStorage', () => {
    const store = useWorkspaceStore.getState()
    store.addPanel({ id: 'conversation' as any, title: 'Test', visible: true })
    store.setActivePanel('conversation')
    const saved = localStorage.getItem('zaram-workspace-layout')
    expect(saved).toBeTruthy()
    const parsed = JSON.parse(saved!)
    expect(parsed.state.layout.panels).toHaveLength(1)
    expect(parsed.state.activePanelId).toBe('conversation')
  })
})
