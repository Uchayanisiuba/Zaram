import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  FolderOpen, FileText, Search, Info, Play, Loader2,
  CheckCircle2, XCircle, ChevronRight, ChevronDown,
  Copy, ExternalLink, FileCode, FileJson, FileType,
  Image as ImageIcon
} from 'lucide-react'
import { desktop } from '@/desktop/desktop-bridge'
import { Button } from '@/components/ui/Button'
import { Markdown } from '@/components/common/Markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'

type FileEntry = {
  name: string
  path: string
  type: 'file' | 'folder'
  size?: number
  modified?: number
  extension?: string
}

type PreviewMode = 'text' | 'markdown' | 'code' | 'image' | 'binary'

export function FilesystemDemo() {
  const [currentPath, setCurrentPath] = useState('')
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [selectedFile, setSelectedFile] = useState<FileEntry | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [previewMode, setPreviewMode] = useState<PreviewMode>('text')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<FileEntry[]>([])
  const [history, setHistory] = useState<FileEntry[]>([])
  const [metadata, setMetadata] = useState<any>(null)

  const waitForExecution = useCallback(async (executionId: string): Promise<any> => {
    return new Promise((resolve, reject) => {
      const unsub = desktop.execution.onEvent((evt: any) => {
        if (evt.executionId === executionId) {
          unsub()
          if (evt.status === 'completed') resolve(evt)
          else if (evt.status === 'failed' || evt.status === 'cancelled') reject(new Error(evt.error?.message || 'Execution failed'))
        }
      })
      desktop.execution.getExecution(executionId).then((status: any) => {
        if (status && status.status === 'completed') {
          unsub()
          resolve(status)
        } else if (status && (status.status === 'failed' || status.status === 'cancelled')) {
          unsub()
          reject(new Error(status.error?.message || 'Execution failed'))
        }
      }).catch(() => {
        // wait for event
      })
    })
  }, [])

  const executeCapability = useCallback(async (capabilityId: string, input: any) => {
    setLoading(true)
    setError(null)
    try {
      const execResult = await desktop.execution.execute(capabilityId, input, {
        timeoutMs: 30000,
        cancellable: true,
        rollbackSupported: true
      })
      if (execResult && execResult.id) {
        const status = await waitForExecution(execResult.id)
        return status.output
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
    return null
  }, [waitForExecution])

  const navigateTo = useCallback(async (path: string) => {
    setCurrentPath(path)
    setSelectedFile(null)
    setPreview(null)
    setMetadata(null)
    setSearchResults([])
    setSearchQuery('')
    const output = await executeCapability('filesystem.listdir', { path })
    if (output && Array.isArray(output)) {
      const mapped: FileEntry[] = output.map((item: any) => ({
        name: item.name || item,
        path: item.path || `${path}/${item.name || item}`,
        type: item.type || (item.name ? (item.name.includes('.') ? 'file' : 'folder') : 'folder'),
        size: item.size,
        modified: item.modified,
        extension: item.extension || (item.name ? item.name.split('.').pop() : undefined),
      }))
      setEntries(mapped)
    }
  }, [executeCapability])

  const openFolder = useCallback(async (entry: FileEntry) => {
    await navigateTo(entry.path)
  }, [navigateTo])

  const selectFile = useCallback(async (entry: FileEntry) => {
    setSelectedFile(entry)
    setPreview(null)
    setMetadata(null)
    const output = await executeCapability('filesystem.read', { path: entry.path })
    if (output !== null) {
      setPreview(typeof output === 'string' ? output : JSON.stringify(output, null, 2))
      const ext = entry.extension?.toLowerCase()
      if (['md', 'markdown'].includes(ext || '')) setPreviewMode('markdown')
      else if (['json', 'js', 'ts', 'tsx', 'jsx', 'py', 'rs', 'go', 'java', 'c', 'cpp', 'h', 'cs', 'rb', 'php', 'swift', 'kt', 'scala', 'sql', 'sh', 'bash', 'yaml', 'yml', 'toml', 'xml', 'html', 'css', 'scss'].includes(ext || '')) setPreviewMode('code')
      else setPreviewMode('text')
    }
    const meta = await executeCapability('filesystem.metadata', { path: entry.path })
    if (meta) setMetadata(meta)
  }, [executeCapability])

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim() || !currentPath) return
    const output = await executeCapability('filesystem.search', { rootPath: currentPath, query: searchQuery })
    if (output && Array.isArray(output)) {
      const mapped: FileEntry[] = output.map((item: any) => ({
        name: item.name || item,
        path: item.path || item,
        type: 'file',
        extension: item.extension || (item.name ? item.name.split('.').pop() : undefined),
      }))
      setSearchResults(mapped)
    }
  }, [searchQuery, currentPath, executeCapability])

  const revealInExplorer = useCallback(async (path: string) => {
    if (desktop.shell?.showItemInFolder) {
      await desktop.shell.showItemInFolder(path)
    }
  }, [])

  const copyPath = useCallback(async (path: string) => {
    if (desktop.clipboard?.writeText) {
      await desktop.clipboard.writeText(path)
    }
  }, [])

  const fileIcon = (entry: FileEntry) => {
    if (entry.type === 'folder') return <FolderOpen className="w-4 h-4 text-blue-400" />
    const ext = entry.extension?.toLowerCase()
    if (['md', 'markdown'].includes(ext || '')) return <FileType className="w-4 h-4 text-purple-400" />
    if (['json', 'js', 'ts', 'tsx', 'jsx'].includes(ext || '')) return <FileJson className="w-4 h-4 text-yellow-400" />
    if (['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'].includes(ext || '')) return <ImageIcon className="w-4 h-4 text-pink-400" />
    if (['py', 'rs', 'go', 'java', 'c', 'cpp'].includes(ext || '')) return <FileCode className="w-4 h-4 text-green-400" />
    return <FileText className="w-4 h-4 text-slate-400" />
  }

  const renderPreview = () => {
    if (!preview && !selectedFile) {
      return (
        <div className="flex items-center justify-center h-full">
          <div className="text-center">
            <FolderOpen className="w-12 h-12 mx-auto mb-4 text-slate-600" />
            <p className="text-slate-400 text-sm">Select a file to preview</p>
          </div>
        </div>
      )
    }
    if (!preview) return null

    if (previewMode === 'markdown') {
      return <Markdown content={preview} />
    }
    if (previewMode === 'code' && selectedFile?.extension) {
      const ext = selectedFile.extension.toLowerCase()
      const langMap: Record<string, string> = {
        js: 'javascript', ts: 'typescript', tsx: 'typescript', jsx: 'javascript',
        py: 'python', rs: 'rust', go: 'go', java: 'java', c: 'c', cpp: 'cpp',
        json: 'json', yaml: 'yaml', yml: 'yaml', xml: 'xml', html: 'html',
        css: 'css', scss: 'scss', sql: 'sql', sh: 'bash', bash: 'bash'
      }
      return (
        <SyntaxHighlighter
          style={vscDarkPlus}
          language={langMap[ext] || 'text'}
          PreTag="div"
          className="text-xs rounded-lg"
        >
          {preview}
        </SyntaxHighlighter>
      )
    }
    return (
      <pre className="text-xs font-mono text-slate-300 whitespace-pre-wrap">
        {preview}
      </pre>
    )
  }

  useEffect(() => {
    navigateTo('.')
  }, [])

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div>
          <h2 className="text-lg font-bold text-white tracking-wide">FILESYSTEM</h2>
          <p className="text-xs text-slate-400 mt-1">Read-only workspace explorer via Filesystem Capability Pack</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-slate-500 uppercase tracking-wider">Executive → Capability → Execution → Filesystem</span>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        <div className="w-80 border-r border-white/5 flex flex-col">
          <div className="px-4 py-3 border-b border-white/5">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">Explorer</h3>
          </div>
          <div className="px-3 py-2 border-b border-white/5">
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search files..."
                className="flex-1 px-2 py-1 bg-white/5 border border-white/10 rounded text-xs focus:outline-none focus:border-white/20"
              />
              <Button variant="ghost" size="sm" onClick={handleSearch} disabled={!searchQuery.trim()}>
                <Search className="w-3 h-3" />
              </Button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {searchQuery && searchResults.length > 0 && (
              <div className="space-y-1">
                <p className="text-[10px] text-slate-500 uppercase tracking-wider px-2">Search Results</p>
                {searchResults.map((entry, i) => (
                  <button
                    key={i}
                    onClick={() => selectFile(entry)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors ${selectedFile?.path === entry.path ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-white hover:bg-white/5'}`}
                  >
                    <div className="flex items-center gap-2">
                      {fileIcon(entry)}
                      <span className="truncate">{entry.name}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
            {entries.map((entry, i) => (
              <button
                key={i}
                onClick={() => entry.type === 'folder' ? openFolder(entry) : selectFile(entry)}
                className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors ${selectedFile?.path === entry.path ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-white hover:bg-white/5'}`}
              >
                <div className="flex items-center gap-2">
                  {entry.type === 'folder' ? <ChevronRight className="w-3 h-3 text-slate-500" /> : fileIcon(entry)}
                  <span className="truncate">{entry.name}</span>
                </div>
              </button>
            ))}
            {!loading && entries.length === 0 && !searchQuery && (
              <p className="text-[10px] text-slate-500 text-center py-4">No files in current directory</p>
            )}
          </div>
        </div>

        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-6">
            {error && (
              <div className="mb-4 p-3 rounded-lg bg-red-400/10 border border-red-400/20 flex items-center gap-2">
                <XCircle className="w-4 h-4 text-red-400" />
                <p className="text-xs text-red-300">{error}</p>
                <Button variant="ghost" size="sm" onClick={() => setError(null)} className="ml-auto">
                  Dismiss
                </Button>
              </div>
            )}
            {loading && !preview && (
              <div className="flex items-center justify-center h-full">
                <div className="flex items-center gap-2 text-slate-400">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm">Loading...</span>
                </div>
              </div>
            )}
            {selectedFile && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {fileIcon(selectedFile)}
                    <span className="text-sm font-mono text-white">{selectedFile.name}</span>
                    <span className="text-[10px] text-slate-500">{selectedFile.path}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={() => copyPath(selectedFile.path)}>
                      <Copy className="w-3 h-3 mr-1" /> Copy Path
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => revealInExplorer(selectedFile.path)}>
                      <ExternalLink className="w-3 h-3 mr-1" /> Reveal
                    </Button>
                  </div>
                </div>
                {metadata && (
                  <div className="glass rounded-xl p-4 border border-white/10">
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider mb-3">Metadata</h3>
                    <div className="grid grid-cols-3 gap-3">
                      <div>
                        <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Size</p>
                        <p className="text-xs font-mono text-white">{metadata.size ? `${metadata.size} bytes` : '--'}</p>
                      </div>
                      <div>
                        <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Modified</p>
                        <p className="text-xs font-mono text-white">{metadata.modified ? new Date(metadata.modified).toLocaleString() : '--'}</p>
                      </div>
                      <div>
                        <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Type</p>
                        <p className="text-xs font-mono text-white">{selectedFile.type}</p>
                      </div>
                    </div>
                  </div>
                )}
                <div className="glass rounded-xl p-4 border border-white/10">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider">Preview</h3>
                    <span className="text-[10px] text-slate-500 capitalize">{previewMode}</span>
                  </div>
                  <div className="max-h-[500px] overflow-auto">
                    {renderPreview()}
                  </div>
                </div>
              </div>
            )}
            {!selectedFile && !loading && (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <FolderOpen className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                  <p className="text-slate-400 text-sm">Select a file to preview</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
