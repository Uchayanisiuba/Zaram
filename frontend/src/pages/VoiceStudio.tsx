import { motion } from 'framer-motion'
import { Play, Pause, Volume2 } from 'lucide-react'
import { useModelStore } from '@/stores/modelStore'
import { useThemeStore } from '@/stores/themeStore'
import { TopBar } from '@/components/layout/TopBar'

export function VoiceStudio() {
  const { voices, currentVoice, setCurrentVoice } = useModelStore()
  const { setTheme } = useThemeStore()

  const handleVoiceSelect = (voice: typeof voices[0]) => {
    setCurrentVoice(voice)
    setTheme(voice.theme as any)
  }

  return (
    <div className="flex flex-col h-screen bg-background">
      <TopBar />
      <div className="flex-1 p-8 overflow-y-auto">
        <h1 className="text-3xl font-bold mb-2">Voice Studio</h1>
        <p className="text-muted-foreground mb-8">Choose your AI assistant's voice personality</p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {voices.map((voice) => (
            <motion.div
              key={voice.id}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className={`glass rounded-xl p-6 cursor-pointer transition-all ${
                currentVoice?.id === voice.id ? 'ring-2 ring-cyan-500' : ''
              }`}
              onClick={() => handleVoiceSelect(voice)}
            >
              <div className="flex items-start gap-4 mb-4">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-2xl font-bold">
                  {voice.name[0]}
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold">{voice.name}</h3>
                  <p className="text-sm text-muted-foreground">{voice.accent}</p>
                  <span className="inline-block mt-1 px-2 py-0.5 rounded text-xs bg-white/5">
                    {voice.gender}
                  </span>
                </div>
              </div>

              <p className="text-sm text-muted-foreground mb-4">{voice.description}</p>

              <button className="w-full py-2 rounded-lg bg-white/5 hover:bg-white/10 transition-colors flex items-center justify-center gap-2">
                <Play className="w-4 h-4" />
                Preview Voice
              </button>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  )
}