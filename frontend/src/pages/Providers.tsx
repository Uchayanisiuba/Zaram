import { motion } from 'framer-motion'
import { Cloud, Server, Check, X } from 'lucide-react'
import { TopBar } from '@/components/layout/TopBar'

export function Providers() {
  const mockProviders = [
    { id: '1', name: 'Ollama', type: 'local' as const, status: 'connected' as const, latency: 12 },
    { id: '2', name: 'OpenAI', type: 'cloud' as const, status: 'disconnected' as const },
    { id: '3', name: 'Anthropic', type: 'cloud' as const, status: 'disconnected' as const },
    { id: '4', name: 'Google', type: 'cloud' as const, status: 'disconnected' as const },
  ]

  return (
    <div className="flex flex-col h-screen bg-background">
      <TopBar />
      <div className="flex-1 p-8 overflow-y-auto">
        <h1 className="text-3xl font-bold mb-2">AI Providers</h1>
        <p className="text-muted-foreground mb-8">Connect to local and cloud AI services</p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {mockProviders.map((provider) => (
            <motion.div
              key={provider.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass rounded-xl p-6"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  {provider.type === 'local' ? (
                    <Server className="w-8 h-8 text-cyan-500" />
                  ) : (
                    <Cloud className="w-8 h-8 text-orange-500" />
                  )}
                  <div>
                    <h3 className="text-lg font-semibold">{provider.name}</h3>
                    <p className="text-sm text-muted-foreground capitalize">{provider.type}</p>
                  </div>
                </div>
                {provider.status === 'connected' ? (
                  <Check className="w-5 h-5 text-green-500" />
                ) : (
                  <X className="w-5 h-5 text-red-500" />
                )}
              </div>

              {provider.latency && (
                <div className="text-sm text-muted-foreground mb-4">
                  Latency: {provider.latency}ms
                </div>
              )}

              <button className="w-full py-2 rounded-lg bg-white/5 hover:bg-white/10 transition-colors">
                {provider.status === 'connected' ? 'Disconnect' : 'Connect'}
              </button>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  )
}