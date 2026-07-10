import { Message, Model, Provider, Voice } from '@/types'

export const mockChatService = {
  async sendMessage(text: string, modelId: string): Promise<Message> {
    await new Promise(resolve => setTimeout(resolve, 1000))
    return {
      id: Date.now().toString(),
      role: 'assistant',
      content: `Mock response to: ${text}`,
      timestamp: new Date(),
      model: modelId,
    }
  },
}

export const mockModelService = {
  async getModels(): Promise<Model[]> {
    await new Promise(resolve => setTimeout(resolve, 500))
    return []
  },
}

export const mockProviderService = {
  async getProviders(): Promise<Provider[]> {
    await new Promise(resolve => setTimeout(resolve, 500))
    return []
  },
}

export const mockVoiceService = {
  async getVoices(): Promise<Voice[]> {
    await new Promise(resolve => setTimeout(resolve, 500))
    return []
  },
}