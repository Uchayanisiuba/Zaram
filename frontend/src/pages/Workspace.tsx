import { CosmicCore } from '@/components/workspace/CosmicCore'
import { ChatWindow } from '@/components/workspace/ChatWindow'
import { InputArea } from '@/components/workspace/InputArea'
import { RightPanel } from '@/components/workspace/RightPanel'
import { TopBar } from '@/components/layout/TopBar'

export function Workspace() {
  return (
    <div className="flex flex-col h-screen bg-background">
      <TopBar />
      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 flex flex-col">
          <div className="flex-1 flex items-center justify-center p-8">
            <CosmicCore />
          </div>
          <ChatWindow />
          <InputArea />
        </div>
        <RightPanel />
      </div>
    </div>
  )
}