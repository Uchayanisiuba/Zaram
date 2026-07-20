import { motion } from 'framer-motion'
import { Cpu, Brain, Code, Eye, Check, X } from 'lucide-react'
import { useModelStore } from '@/stores/modelStore'
import { TopBar } from '@/components/layout/TopBar'

export function Models() {
  const { models, currentModel, setCurrentModel } = useModelStore()

  const capabilityIcons = {
    reasoning: Brain,
    coding: Code,
    vision: Eye,
  }

  return (
    <div className="flex flex-col h-screen bg-background">
      <TopBar />
      <div className="flex-1 p-8 overflow-y-auto">
        <h1 className="text-3xl font-bold mb-8">AI Models</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {models.map((model) => (
            <motion.div
              key={model.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className={`glass rounded-xl p-6 cursor-pointer transition-all ${
                currentModel?.id === model.id ? 'ring-2 ring-cyan-500' : ''
              }`}
              onClick={() => setCurrentModel(model)}
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-lg font-semibold">{model.name}</h3>
                  <p className="text-sm text-muted-foreground">{model.provider}</p>
                </div>
                {model.status === 'active' ? (
                  <Check className="w-5 h-5 text-green-500" />
                ) : (
                  <X className="w-5 h-5 text-red-500" />
                )}
              </div>
              
              <div className="space-y-2 mb-4">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Cpu className="w-4 h-4" />
                  <span>{model.ram ?? 'N/A'}</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Brain className="w-4 h-4" />
                  <span>{(model.contextLength ?? 0).toLocaleString()} tokens</span>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                {(model.capabilities ?? []).map((cap) => {
                  const Icon = capabilityIcons[cap as keyof typeof capabilityIcons]
                  return (
                    <span key={cap} className="px-2 py-1 rounded-md bg-white/5 text-xs">
                      {Icon && <Icon className="w-3 h-3 inline mr-1" />}
                      {cap}
                    </span>
                  )
                })}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  )
}