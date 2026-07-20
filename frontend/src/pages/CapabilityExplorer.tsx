import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  Search, Filter, Shield, Clock, Cpu, Globe,
  ChevronRight, Info, Activity, BarChart3,
  PlayCircle, CheckCircle2, XCircle
} from 'lucide-react'
import { desktop } from '@/desktop/desktop-bridge'
import { Button } from '@/components/ui/Button'

type CapabilityCategory = 'system' | 'workspace' | 'filesystem' | 'communication' | 'ai' | 'automation' | 'developer' | 'media' | 'vision' | 'speech' | 'plugins' | 'security'

interface CapabilityDescriptor {
  id: string
  name: string
  description: string
  category: CapabilityCategory
  permissions: string[]
  availability: string
  latencyEstimateMs: number
  location: string
  cost: number
  enabled: boolean
  source?: string
  tags?: string[]
  revision: number
  updatedAt: number
}

interface CapabilityDetail extends CapabilityDescriptor {
  status: string
  calls?: number
  averageTimeMs?: number
  lastUsed?: number
  lastExecution?: any
  evidence?: string[]
}

export function CapabilityExplorer() {
  const [capabilities, setCapabilities] = useState<CapabilityDescriptor[]>([])
  const [filtered, setFiltered] = useState<CapabilityDescriptor[]>([])
  const [selected, setSelected] = useState<CapabilityDetail | null>(null)
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<CapabilityCategory | 'all'>('all')
  const [loading, setLoading] = useState(true)
  const [metrics, setMetrics] = useState<Record<string, any>>({})

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const snap = await desktop.capability.getSnapshot()
      const caps = (snap as any)?.capabilities || []
      setCapabilities(caps)
      setFiltered(caps)

      const execHistory = await desktop.execution.getHistory()
      const metricsMap: Record<string, any> = {}
      for (const exec of (execHistory || [])) {
        const id = exec.capabilityId
        if (!metricsMap[id]) {
          metricsMap[id] = { calls: 0, totalTime: 0, lastUsed: exec.finishedAt || exec.startedAt }
        }
        metricsMap[id].calls += 1
        metricsMap[id].totalTime += exec.durationMs || 0
        const lastUsed = exec.finishedAt || exec.startedAt
        if (lastUsed && (!metricsMap[id].lastUsed || lastUsed > metricsMap[id].lastUsed)) {
          metricsMap[id].lastUsed = lastUsed
        }
      }
      setMetrics(metricsMap)
    } catch {
      // ignore
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    load()
    const unsub = desktop.execution.onEvent(() => {
      load()
    })
    return unsub
  }, [load])

  useEffect(() => {
    let result = capabilities
    if (categoryFilter !== 'all') {
      result = result.filter(c => c.category === categoryFilter)
    }
    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(c =>
        c.name.toLowerCase().includes(q) ||
        c.id.toLowerCase().includes(q) ||
        c.description.toLowerCase().includes(q)
      )
    }
    setFiltered(result)
  }, [search, categoryFilter, capabilities])

  const categories: (CapabilityCategory | 'all')[] = ['all', 'system', 'workspace', 'filesystem', 'communication', 'ai', 'automation', 'developer', 'media', 'vision', 'speech', 'plugins', 'security']

  const statusFromAvailability = (avail: string): string => {
    switch (avail) {
      case 'available': return 'Healthy'
      case 'unavailable': return 'Unavailable'
      case 'disabled': return 'Disabled'
      case 'requires-setup': return 'Needs Setup'
      case 'degraded': return 'Degraded'
      default: return 'Unknown'
    }
  }

  const statusColor = (status: string) => {
    switch (status) {
      case 'Healthy': return 'text-green-400'
      case 'Unavailable': return 'text-red-400'
      case 'Disabled': return 'text-slate-400'
      case 'Needs Setup': return 'text-yellow-400'
      case 'Degraded': return 'text-orange-400'
      default: return 'text-slate-400'
    }
  }

  const enrichCapability = (cap: CapabilityDescriptor): CapabilityDetail => {
    const m = metrics[cap.id]
    return {
      ...cap,
      status: statusFromAvailability(cap.availability),
      calls: m?.calls || 0,
      averageTimeMs: m?.calls ? Math.round(m.totalTime / m.calls) : cap.latencyEstimateMs,
      lastUsed: m?.lastUsed,
    }
  }

  const handleSelect = async (cap: CapabilityDescriptor) => {
    const enriched = enrichCapability(cap)
    try {
      const execHistory = await desktop.execution.getHistory()
      const lastExec = (execHistory || []).find((e: any) => e.capabilityId === cap.id)
      if (lastExec) {
        enriched.lastExecution = lastExec
      }
      const evidence = await desktop.executive.getEvidence()
      const relevant = evidence.filter((e: string) => e.toLowerCase().includes(cap.name.toLowerCase()) || e.toLowerCase().includes(cap.id.toLowerCase()))
      enriched.evidence = relevant.length > 0 ? relevant : evidence.slice(0, 3)
    } catch {
      // ignore
    }
    setSelected(enriched)
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <div>
          <h2 className="text-lg font-bold text-white tracking-wide">CAPABILITY EXPLORER</h2>
          <p className="text-xs text-slate-400 mt-1">Browse available capabilities</p>
        </div>
        <Button variant="ghost" size="sm" onClick={load} disabled={loading}>
          <Filter className="w-3 h-3 mr-1" /> Refresh
        </Button>
      </div>

      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="px-6 py-4 border-b border-white/5 flex items-center gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search capabilities..."
                className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-sm focus:outline-none focus:border-white/20"
              />
            </div>
            <div className="flex items-center gap-2">
              {categories.map(cat => (
                <button
                  key={cat}
                  onClick={() => setCategoryFilter(cat)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${categoryFilter === cat ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-white hover:bg-white/5'}`}
                >
                  {cat === 'all' ? 'All' : cat}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-6">
            {loading ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-slate-400 text-sm">Loading capabilities...</div>
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <Cpu className="w-12 h-12 mx-auto mb-4 text-slate-600" />
                  <p className="text-slate-400 text-sm">No capabilities found</p>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3">
                {filtered.map((cap, i) => {
                  const enriched = enrichCapability(cap)
                  return (
                    <motion.button
                      key={cap.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.02 }}
                      onClick={() => handleSelect(cap)}
                      className={`w-full text-left glass rounded-xl p-4 border transition-colors ${selected?.id === cap.id ? 'border-white/30 bg-white/10' : 'border-white/10 hover:border-white/20'}`}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <h3 className="text-sm font-bold text-white">{cap.name}</h3>
                          <p className="text-[10px] font-mono text-slate-400 mt-0.5">{cap.id}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded ${enriched.status === 'Healthy' ? 'bg-green-400/10 text-green-400' : enriched.status === 'Unavailable' ? 'bg-red-400/10 text-red-400' : 'bg-slate-400/10 text-slate-400'}`}>
                            {enriched.status}
                          </span>
                          <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded ${cap.enabled ? 'bg-green-400/10 text-green-400' : 'bg-slate-400/10 text-slate-400'}`}>
                            {cap.enabled ? 'Enabled' : 'Disabled'}
                          </span>
                        </div>
                      </div>
                      <p className="text-xs text-slate-400 mb-3 line-clamp-2">{cap.description}</p>
                      <div className="flex items-center gap-4 text-[10px] text-slate-500">
                        <span className="px-2 py-0.5 rounded bg-white/5 capitalize">{cap.category}</span>
                        <span className={`capitalize ${statusColor(enriched.status)}`}>{enriched.availability}</span>
                        <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {enriched.averageTimeMs}ms</span>
                        <span className="flex items-center gap-1"><Activity className="w-3 h-3" /> {enriched.calls} calls</span>
                        {enriched.lastUsed && (
                          <span className="flex items-center gap-1"><PlayCircle className="w-3 h-3" /> {new Date(enriched.lastUsed).toLocaleTimeString()}</span>
                        )}
                      </div>
                    </motion.button>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {selected && (
          <div className="w-96 border-l border-white/5 flex flex-col overflow-hidden">
            <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">Capability Details</h3>
              <button onClick={() => setSelected(null)} className="text-slate-400 hover:text-white text-xs">Close</button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <div>
                <h4 className="text-sm font-bold text-white mb-1">{selected.name}</h4>
                <p className="text-[10px] font-mono text-slate-400">{selected.id}</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Description</p>
                <p className="text-xs text-slate-300">{selected.description}</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Status</p>
                  <p className={`text-xs font-mono capitalize ${statusColor(selected.status)}`}>{selected.status}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Category</p>
                  <p className="text-xs font-mono text-white capitalize">{selected.category}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Location</p>
                  <p className="text-xs font-mono text-white capitalize">{selected.location}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Latency</p>
                  <p className="text-xs font-mono text-white">{selected.latencyEstimateMs}ms</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Calls</p>
                  <p className="text-xs font-mono text-white">{selected.calls || 0}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Average Time</p>
                  <p className="text-xs font-mono text-white">{selected.averageTimeMs || '--'}ms</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Cost</p>
                  <p className="text-xs font-mono text-white">{(selected.cost * 100).toFixed(0)}%</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Revision</p>
                  <p className="text-xs font-mono text-white">{selected.revision}</p>
                </div>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Permissions</p>
                <div className="flex flex-wrap gap-1">
                  {selected.permissions.map(p => (
                    <span key={p} className="px-2 py-0.5 rounded bg-white/5 text-[10px] font-mono text-slate-300 flex items-center gap-1">
                      <Shield className="w-3 h-3" /> {p}
                    </span>
                  ))}
                </div>
              </div>
              {selected.tags && selected.tags.length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Tags</p>
                  <div className="flex flex-wrap gap-1">
                    {selected.tags.map(t => (
                      <span key={t} className="px-2 py-0.5 rounded bg-white/5 text-[10px] text-slate-300">{t}</span>
                    ))}
                  </div>
                </div>
              )}
              <div>
                <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Last Updated</p>
                <p className="text-xs font-mono text-white">{new Date(selected.updatedAt).toLocaleString()}</p>
              </div>
              {selected.lastUsed && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Last Used</p>
                  <p className="text-xs font-mono text-white">{new Date(selected.lastUsed).toLocaleString()}</p>
                </div>
              )}
              {selected.lastExecution && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Last Execution</p>
                  <div className="bg-black/30 rounded-lg p-3 space-y-1">
                    <div className="flex items-center gap-2">
                      {selected.lastExecution.status === 'completed' ? (
                        <CheckCircle2 className="w-3 h-3 text-green-400" />
                      ) : selected.lastExecution.status === 'failed' ? (
                        <XCircle className="w-3 h-3 text-red-400" />
                      ) : (
                        <Clock className="w-3 h-3 text-slate-400" />
                      )}
                      <span className="text-xs font-mono text-white">{selected.lastExecution.status}</span>
                      <span className="text-[10px] text-slate-500">{selected.lastExecution.durationMs}ms</span>
                    </div>
                    <p className="text-[10px] text-slate-400 font-mono truncate">
                      Input: {JSON.stringify(selected.lastExecution.input).slice(0, 100)}
                    </p>
                    {selected.lastExecution.output && (
                      <p className="text-[10px] text-green-300 font-mono truncate">
                        Output: {typeof selected.lastExecution.output === 'string' ? selected.lastExecution.output.slice(0, 100) : JSON.stringify(selected.lastExecution.output).slice(0, 100)}
                      </p>
                    )}
                  </div>
                </div>
              )}
              {selected.evidence && selected.evidence.length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Evidence</p>
                  <div className="space-y-1">
                    {selected.evidence.map((item, i) => (
                      <p key={i} className="text-xs text-slate-400 bg-white/5 rounded px-2 py-1">- {item}</p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
