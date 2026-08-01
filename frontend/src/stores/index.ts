// === ORB DOMAIN ===
export { useOrbStore } from './orbStore';
export { useFrameStore } from './frameStore';

// === CONVERSATION DOMAIN ===
export { useConversationStore } from './conversationStore';
export type { Message } from './conversationStore';

// === WORKSPACE DOMAIN ===
export { useWorkspaceStore } from './workspaceStore';
export { useCameraStore } from './cameraStore';
export { useSurfaceStore } from './surfaceStore';

// === UI DOMAIN ===
export { useShellStore } from './shellStore';
export { usePaletteStore } from './paletteStore';
export { useSettingsStore } from './settingsStore';

// === RUNTIME DOMAIN ===
export { useRuntimeStore } from './runtimeStore';