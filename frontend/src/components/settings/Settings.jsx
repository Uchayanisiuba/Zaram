import { useZaram } from '../../hooks/useZaram';

const CHARACTERS = {
  zaram_prime: { name: '🧠 Zaram Prime', description: 'Primary cybernetic intelligence core. Warm, fast, highly structured.' },
  nova_hacker: { name: '⚡ Nova', description: 'Fast-paced code analysis agent with a sharp, technical voice.' },
  baba_elder: { name: '🧙 Baba', description: 'Wise elder voice. Calm, analytical, focused on deep systems logic.' },
  michael_tech: { name: '🤖 Michael', description: 'Operational support unit. Concise and professional.' },
};

const MODELS = [
  { id: 'auto', name: 'Auto Router', description: 'Intelligently routes to best model for the task' },
  { id: 'qwen3:latest', name: 'Qwen 3', description: 'Advanced reasoning, code, complex analysis' },
  { id: 'gemma3:latest', name: 'Gemma 3', description: 'Logic, mathematics, analytical thinking' },
  { id: 'llama3.2:latest', name: 'Llama 3.2', description: 'Conversational, natural dialogue' },
  { id: 'moondream:latest', name: 'Moondream', description: 'Vision, image understanding, OCR' },
];

export const Settings = () => {
  const {
    selectedCharacter,
    setSelectedCharacter,
    selectedModel,
    setSelectedModel,
  } = useZaram();

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-2xl mx-auto p-6 space-y-8">
        
        {/* Header */}
        <div>
          <h2 className="text-2xl font-bold text-slate-100 mb-2">Settings</h2>
          <p className="text-slate-400">Configure your Zaram experience</p>
        </div>

        {/* Character Selection */}
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-semibold text-slate-100 mb-4">Select Persona</h3>
            <p className="text-sm text-slate-400 mb-4">Choose the voice and personality of your AI assistant</p>
          </div>

          <div className="grid gap-3">
            {Object.entries(CHARACTERS).map(([id, char]) => (
              <button
                key={id}
                onClick={() => setSelectedCharacter(id)}
                className={`p-4 rounded-lg border transition-all text-left ${
                  selectedCharacter === id
                    ? 'bg-cyan-600/20 border-cyan-500/50 shadow-lg shadow-cyan-500/20'
                    : 'bg-slate-800/30 border-slate-700/30 hover:border-cyan-500/30'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-slate-100">{char.name}</p>
                    <p className="text-sm text-slate-400 mt-1">{char.description}</p>
                  </div>
                  {selectedCharacter === id && (
                    <svg className="w-5 h-5 text-cyan-400 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                    </svg>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Model Selection */}
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-semibold text-slate-100 mb-4">Select Model</h3>
            <p className="text-sm text-slate-400 mb-4">Choose the AI model for reasoning and responses</p>
          </div>

          <div className="grid gap-3">
            {MODELS.map(model => (
              <button
                key={model.id}
                onClick={() => setSelectedModel(model.id)}
                className={`p-4 rounded-lg border transition-all text-left ${
                  selectedModel === model.id
                    ? 'bg-cyan-600/20 border-cyan-500/50 shadow-lg shadow-cyan-500/20'
                    : 'bg-slate-800/30 border-slate-700/30 hover:border-cyan-500/30'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-slate-100">{model.name}</p>
                    <p className="text-sm text-slate-400 mt-1">{model.description}</p>
                  </div>
                  {selectedModel === model.id && (
                    <svg className="w-5 h-5 text-cyan-400 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                    </svg>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* System Info */}
        <div className="border-t border-cyan-950/30 pt-6">
          <h3 className="text-lg font-semibold text-slate-100 mb-4">System Info</h3>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between p-3 bg-slate-800/30 rounded-lg border border-slate-700/30">
              <span className="text-slate-400">Version</span>
              <span className="text-slate-100 font-medium">2.0</span>
            </div>
            <div className="flex justify-between p-3 bg-slate-800/30 rounded-lg border border-slate-700/30">
              <span className="text-slate-400">Backend</span>
              <span className="text-slate-100 font-medium">FastAPI 🚀</span>
            </div>
            <div className="flex justify-between p-3 bg-slate-800/30 rounded-lg border border-slate-700/30">
              <span className="text-slate-400">Frontend</span>
              <span className="text-slate-100 font-medium">React 18 + Tailwind</span>
            </div>
            <div className="flex justify-between p-3 bg-slate-800/30 rounded-lg border border-slate-700/30">
              <span className="text-slate-400">Status</span>
              <span className="text-green-400 font-medium">✓ Running</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
