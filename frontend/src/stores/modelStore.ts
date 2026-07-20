import { create } from 'zustand'
import type { Model, Provider, Voice } from '@/types'

interface ModelState {
  models: Model[]
  providers: Provider[]
  voices: Voice[]
  currentModel: Model | null
  currentProvider: Provider | null
  currentVoice: Voice | null
  setCurrentModel: (model: Model) => void
  setCurrentVoice: (voice: Voice) => void
  setModels: (models: Model[]) => void
  setProviders: (providers: Provider[]) => void
  setVoices: (voices: Voice[]) => void
}

export const useModelStore = create<ModelState>((set) => ({
  models: [],
  providers: [],
  voices: [],
  currentModel: null,
  currentProvider: null,
  currentVoice: null,
  setCurrentModel: (model) => set({ currentModel: model }),
  setCurrentVoice: (voice) => set({ currentVoice: voice }),
  setModels: (models) => set({ models }),
  setProviders: (providers) => set({ providers }),
  setVoices: (voices) => set({ voices }),
}))
