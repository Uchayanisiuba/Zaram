import { useZaram } from '../../hooks/useZaram';

const MODELS = [
  { id: 'auto', name: 'Auto Router', description: 'Intelligently routes to best model for the task' },
  { id: 'qwen3:latest', name: 'Qwen 3', description: 'Advanced reasoning, code, complex analysis' },
  { id: 'gemma3:latest', name: 'Gemma 3', description: 'Logic, mathematics, analytical thinking' },
  { id: 'llama3.2:latest', name: 'Llama 3.2', description: 'Conversational, natural dialogue' },
  { id: 'qwen2.5vl:7b', name: 'Qwen 2.5 VL 7B', description: 'Vision, image understanding, OCR (Default)' },
  { id: 'moondream:latest', name: 'Moondream', description: 'Vision, image understanding, OCR (Fallback)' },
]

const PERSONAS = [
  { id: 'zaram_prime', name: 'Zaram Prime', description: 'Professional, calm, and authoritative' },
  { id: 'baba', name: 'Baba', description: 'Wise elder voice. Calm, analytical, focused on deep systems logic' },
  { id: 'nova', name: 'Nova', description: 'Fast-paced code analysis agent with a sharp, technical voice' },
  { id: 'mentor', name: 'Mentor', description: 'Patient teacher. Explains concepts clearly and encourages learning' },
  { id: 'creator', name: 'Creator', description: 'Creative and expressive. Helps with writing, design, and creative projects' },
  { id: 'analyst', name: 'Analyst', description: 'Data-driven and precise. Focuses on facts, metrics, and objective analysis' },
  { id: 'researcher', name: 'Researcher', description: 'Thorough investigator. Deep dives into topics and synthesizes information' },
  { id: 'minimal', name: 'Minimal', description: 'Concise and efficient. Short answers, no fluff' },
];

const SECTIONS = [
  { id: 'ai', label: 'AI', description: 'Models, personas, voice, and reasoning' },
  { id: 'connections', label: 'Connections', description: 'Projects, browser, documents, and integrations' },
  { id: 'knowledge', label: 'Knowledge', description: 'Internet access, search, and memory' },
  { id: 'memory', label: 'Memory', description: 'Long-term memory and knowledge bases' },
  { id: 'vision', label: 'Vision', description: 'Camera, screen sharing, OCR, and models' },
  { id: 'presence', label: 'Presence', description: 'Living Orb, MetaHuman, and animations' },
  { id: 'privacy', label: 'Privacy', description: 'Offline mode, permissions, and data' },
]

const INTERNET_OPTIONS = [
  { id: 'never', label: 'Never', description: 'Completely offline mode' },
  { id: 'ask', label: 'Ask Every Time', description: 'Prompt before internet access' },
  { id: 'automatic', label: 'Automatic', description: 'Executive decides when to search' },
  { id: 'always', label: 'Always', description: 'Always allow internet access' },
]

export const Settings = () => {
  const {
    selectedModel,
    setSelectedModel,
    selectedCharacter,
    setSelectedCharacter,
  } = useZaram();

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-8">
        
        {/* Header */}
        <div>
          <h2 className="text-2xl font-bold text-slate-100 mb-2">HQ</h2>
          <p className="text-slate-400">Command Center — configure every layer of Zaram OS</p>
        </div>

        {/* Quick Access Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {SECTIONS.map(section => (
            <button
              key={section.id}
              className="p-4 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 hover:border-cyan-500/30 transition-all text-left group"
            >
              <h3 className="text-sm font-semibold text-slate-100 group-hover:text-cyan-400 transition-colors">{section.label}</h3>
              <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">{section.description}</p>
            </button>
          ))}
        </div>

        {/* AI Section */}
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-semibold text-slate-100 mb-1">AI</h3>
            <p className="text-sm text-slate-400">Select the model for reasoning and responses</p>
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

        {/* Persona Section */}
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-semibold text-slate-100 mb-1">Persona</h3>
            <p className="text-sm text-slate-400">Choose how Zaram thinks and responds</p>
          </div>

          <div className="grid gap-3">
            {PERSONAS.map(persona => (
              <button
                key={persona.id}
                onClick={() => setSelectedCharacter(persona.id)}
                className={`p-4 rounded-lg border transition-all text-left ${
                  selectedCharacter === persona.id
                    ? 'bg-cyan-600/20 border-cyan-500/50 shadow-lg shadow-cyan-500/20'
                    : 'bg-slate-800/30 border-slate-700/30 hover:border-cyan-500/30'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-slate-100">{persona.name}</p>
                    <p className="text-sm text-slate-400 mt-1">{persona.description}</p>
                  </div>
                  {selectedCharacter === persona.id && (
                    <svg className="w-5 h-5 text-cyan-400 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                    </svg>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Knowledge Section */}
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-semibold text-slate-100 mb-1">Knowledge</h3>
            <p className="text-sm text-slate-400">Control how Zaram accesses the internet</p>
          </div>

          <div className="space-y-2">
            {INTERNET_OPTIONS.map(option => (
              <label
                key={option.id}
                className="flex items-start gap-3 p-4 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 cursor-pointer transition-colors"
              >
                <input
                  type="radio"
                  name="internet-access"
                  defaultChecked={option.id === 'automatic'}
                  className="mt-1"
                />
                <div>
                  <p className="font-medium text-slate-100">{option.label}</p>
                  <p className="text-sm text-slate-400">{option.description}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Connections Section */}
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-semibold text-slate-100 mb-1">Connections</h3>
            <p className="text-sm text-slate-400">Manage your connected services</p>
          </div>

          <div className="grid gap-3">
            <ConnectionCard
              icon="🌐"
              title="Browser"
              status="Connected"
              actions={['Default Browser', 'History Access', 'Bookmarks']}
            />
            <ConnectionCard
              icon="📧"
              title="Email"
              status="Not Connected"
              actions={['Connect Gmail', 'Connect Outlook']}
            />
            <ConnectionCard
              icon="📅"
              title="Calendar"
              status="Not Connected"
              actions={['Google Calendar', 'Outlook Calendar', 'Apple Calendar']}
            />
            <ConnectionCard
              icon="📰"
              title="RSS"
              status="Not Connected"
              actions={['Manage Feeds', 'Add Feed', 'Import OPML']}
            />
            <ConnectionCard
              icon="📷"
              title="Camera"
              status="Available"
              actions={['Camera Permission', 'Preferred Camera']}
            />
            <ConnectionCard
              icon="🖥"
              title="Screen Share"
              status="Available"
              actions={['Permission', 'Active Window', 'Entire Desktop']}
            />
            <ConnectionCard
              icon="⚡"
              title="Automation"
              status="Coming Soon"
              actions={[]}
              disabled
            />
          </div>
        </div>

        {/* Future Placeholders */}
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-semibold text-slate-100 mb-1">Coming Soon</h3>
            <p className="text-sm text-slate-400">These sections are being prepared</p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {['Models', 'Memory', 'Appearance', 'Voice', 'Privacy', 'Plugins'].map(section => (
              <div
                key={section}
                className="p-4 rounded-xl border border-dashed border-white/10 bg-white/5 text-slate-500 text-sm"
              >
                {section}
              </div>
            ))}
          </div>
        </div>

        {/* System Info */}
        <div className="border-t border-cyan-950/30 pt-6">
          <h3 className="text-lg font-semibold text-slate-100 mb-4">System</h3>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between p-3 bg-slate-800/30 rounded-lg border border-slate-700/30">
              <span className="text-slate-400">Version</span>
              <span className="text-slate-100 font-medium">2.0</span>
            </div>
            <div className="flex justify-between p-3 bg-slate-800/30 rounded-lg border border-slate-700/30">
              <span className="text-slate-400">Backend</span>
              <span className="text-slate-100 font-medium">FastAPI</span>
            </div>
            <div className="flex justify-between p-3 bg-slate-800/30 rounded-lg border border-slate-700/30">
              <span className="text-slate-400">Frontend</span>
              <span className="text-slate-100 font-medium">React + Tailwind</span>
            </div>
            <div className="flex justify-between p-3 bg-slate-800/30 rounded-lg border border-slate-700/30">
              <span className="text-slate-400">Status</span>
              <span className="text-green-400 font-medium">Running</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

  function ConnectionCard({ icon, title, status, actions, disabled }) {
  return (
    <div className={`p-4 rounded-lg border border-white/10 bg-white/5 ${disabled ? 'opacity-50' : ''}`}>
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">{icon}</span>
          <h4 className="font-medium text-slate-100">{title}</h4>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full ${
          status === 'Connected' || status === 'Available'
            ? 'bg-green-400/10 text-green-400 border border-green-400/20'
            : status === 'Coming Soon'
            ? 'bg-slate-400/10 text-slate-400 border border-slate-400/20'
            : 'bg-yellow-400/10 text-yellow-400 border border-yellow-400/20'
        }`}>
          {status}
        </span>
      </div>
      {actions.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-3">
          {actions.map(action => (
            <button
              key={action}
              disabled={disabled}
              className="px-3 py-1.5 rounded-lg text-xs border border-white/10 bg-white/5 hover:bg-white/10 text-slate-300 transition-colors disabled:opacity-50"
            >
              {action}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
