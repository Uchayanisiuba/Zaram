/**
 * Quick actions for Computer Use — exposed in Settings and Ambient Panel.
 *
 * These are one-shot MCP calls to cua-driver for common desktop automation
 * tasks. They run through the policy gate (confirm for mutative actions)
 * and are logged in the conversation like any other tool call.
 */
import { useState } from 'react';
import {
  Monitor,
  MousePointerClick,
  Keyboard,
  List,
  Maximize,
  Move,
  RotateCcw,
  RefreshCw,
  Loader2,
  AlertTriangle,
  Check,
} from 'lucide-react';
import { callTool } from '../../services/toolsClient';

interface ComputerUseActionProps {
  serverId: string;
  isHealthy: boolean;
  busy: boolean;
  onActionComplete: () => void;
}

type ActionType =
  | 'screenshot'
  | 'list_windows'
  | 'list_apps'
  | 'get_desktop_state'
  | 'get_window_state'
  | 'click'
  | 'type_text'
  | 'scroll'
  | 'hotkey';

const ACTIONS: Record<
  ActionType,
  { icon: React.ReactNode; label: string; tool: string; description: string; needsTarget: boolean }
> = {
  screenshot: {
    icon: <Monitor size={14} />,
    label: 'Screenshot',
    tool: 'get_desktop_state',
    description: 'Capture full desktop screenshot',
    needsTarget: false,
  },
  list_windows: {
    icon: <List size={14} />,
    label: 'List Windows',
    tool: 'list_windows',
    description: 'Show all open windows with PIDs',
    needsTarget: false,
  },
  list_apps: {
    icon: <RotateCcw size={14} />,
    label: 'List Apps',
    tool: 'list_apps',
    description: 'Show running and installed applications',
    needsTarget: false,
  },
  get_desktop_state: {
    icon: <Monitor size={14} />,
    label: 'Desktop State',
    tool: 'get_desktop_state',
    description: 'Full desktop screenshot + cursor position',
    needsTarget: false,
  },
  get_window_state: {
    icon: <Maximize size={14} />,
    label: 'Window State',
    tool: 'get_window_state',
    description: 'Accessibility tree + screenshot for a window',
    needsTarget: true,
  },
  click: {
    icon: <MousePointerClick size={14} />,
    label: 'Click',
    tool: 'click',
    description: 'Click at coordinates or element',
    needsTarget: true,
  },
  type_text: {
    icon: <Keyboard size={14} />,
    label: 'Type Text',
    tool: 'type_text',
    description: 'Type text into focused element',
    needsTarget: true,
  },
  scroll: {
    icon: <Move size={14} />,
    label: 'Scroll',
    tool: 'scroll',
    description: 'Scroll a window',
    needsTarget: true,
  },
  hotkey: {
    icon: <Keyboard size={14} />,
    label: 'Hotkey',
    tool: 'hotkey',
    description: 'Press key combination (e.g., cmd+c)',
    needsTarget: false,
  },
};

export function ComputerUseAction({ serverId, isHealthy, busy, onActionComplete }: ComputerUseActionProps) {
  const [open, setOpen] = useState(false);
  const [actionResult, setActionResult] = useState<{ tool: string; result?: any; error?: string } | null>(null);
  const [selectedAction, setSelectedAction] = useState<ActionType | null>(null);
  const [targetInput, setTargetInput] = useState('');
  const [actionBusy, setActionBusy] = useState(false);

  const runAction = async (action: ActionType) => {
    if (!isHealthy) {
      setActionResult({ tool: action, error: 'cua-driver is not healthy — check permissions' });
      return;
    }

    const config = ACTIONS[action];
    const needsWindowTarget = action === 'get_window_state' || action === 'click' || action === 'type_text' || action === 'scroll';

    if (needsWindowTarget && !targetInput.trim()) {
      setActionResult({ tool: action, error: 'Enter a window PID or click "List Windows" first' });
      return;
    }

    setActionBusy(true);
    setActionResult(null);

    try {
      let args: Record<string, any> = {};

      if (action === 'get_window_state') {
        const pid = parseInt(targetInput.trim(), 10);
        if (isNaN(pid)) {
          setActionResult({ tool: action, error: 'Invalid PID — must be a number' });
          return;
        }
        args = { pid, include_screenshot: true };
      } else if (action === 'click') {
        // Format: "pid x y" or "pid element_token"
        const parts = targetInput.trim().split(/\s+/);
        const pid = parseInt(parts[0], 10);
        if (isNaN(pid)) {
          setActionResult({ tool: action, error: 'Invalid PID' });
          return;
        }
        args = { pid };
        if (parts.length >= 3) {
          args.x = parseInt(parts[1], 10);
          args.y = parseInt(parts[2], 10);
        } else if (parts.length === 2) {
          args.element_token = parts[1];
        }
      } else if (action === 'type_text') {
        const parts = targetInput.trim().split(/\s+/, 2);
        const pid = parseInt(parts[0], 10);
        if (isNaN(pid)) {
          setActionResult({ tool: action, error: 'Invalid PID' });
          return;
        }
        args = { pid, text: parts[1] ?? '' };
      } else if (action === 'scroll') {
        const parts = targetInput.trim().split(/\s+/);
        const pid = parseInt(parts[0], 10);
        if (isNaN(pid)) {
          setActionResult({ tool: action, error: 'Invalid PID' });
          return;
        }
        args = { pid, direction: parts[1] ?? 'down', pages: parts[2] ? parseInt(parts[2], 10) : 1 };
      } else if (action === 'hotkey') {
        args = { keys: targetInput.trim() };
      }

      const result = await callTool(serverId, config.tool, args);

      setActionResult({ tool: config.tool, result });
      setTargetInput('');
      onActionComplete();
    } catch (err) {
      setActionResult({ tool: config.tool, error: (err as Error).message });
    } finally {
      setActionBusy(false);
    }
  };

  const quickActions: ActionType[] = ['screenshot', 'list_windows', 'list_apps', 'get_desktop_state'];
  const advancedActions: ActionType[] = ['get_window_state', 'click', 'type_text', 'scroll', 'hotkey'];

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        className="text-xs text-left flex items-center gap-2"
        style={{ color: 'var(--color-cyan-light)' }}
        onClick={() => setOpen(!open)}
        disabled={busy}
      >
        {open ? 'Hide quick actions' : 'Show quick actions'}
        <RefreshCw size={12} className={open ? 'rotate-180' : ''} />
      </button>

      {open && (
        <div className="flex flex-col gap-2 pl-3">
          {/* Quick Actions (no target needed) */}
          <div className="flex flex-wrap gap-1.5">
            {quickActions.map((action) => {
              const config = ACTIONS[action];
              return (
                <button
                  key={action}
                  type="button"
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg"
                  style={{
                    background: 'var(--color-glass)',
                    border: '1px solid var(--color-border-subtle)',
                    color: 'var(--color-text)',
                    opacity: busy || actionBusy ? 0.5 : 1,
                  }}
                  onClick={() => runAction(action)}
                  disabled={busy || actionBusy}
                  title={config.description}
                >
                  {config.icon}
                  <span>{config.label}</span>
                </button>
              );
            })}
          </div>

          {/* Advanced Actions (need target) */}
          <div className="flex flex-wrap gap-1.5">
            {advancedActions.map((action) => {
              const config = ACTIONS[action];
              return (
                <button
                  key={action}
                  type="button"
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg"
                  style={{
                    background: 'var(--color-glass)',
                    border: '1px solid var(--color-border-subtle)',
                    color: 'var(--color-text)',
                    opacity: busy || actionBusy ? 0.5 : 1,
                  }}
                  onClick={() => {
                    setSelectedAction(action);
                    setActionResult(null);
                  }}
                  disabled={busy || actionBusy}
                  title={config.description}
                >
                  {config.icon}
                  <span>{config.label}</span>
                </button>
              );
            })}
          </div>

          {/* Target input for advanced actions */}
          {selectedAction && (
            <div className="flex flex-col gap-1.5 pl-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono" style={{ color: 'var(--color-text-muted)' }}>
                  {ACTIONS[selectedAction].label} target:
                </span>
                <input
                  type="text"
                  value={targetInput}
                  onChange={(e) => setTargetInput(e.target.value)}
                  placeholder={
                    selectedAction === 'get_window_state'
                      ? 'PID (e.g., 1234)'
                      : selectedAction === 'click'
                      ? 'PID [x y] or PID element_token (e.g., "1234 100 200" or "1234 s000b:42")'
                      : selectedAction === 'type_text'
                      ? 'PID text (e.g., "1234 hello world")'
                      : selectedAction === 'scroll'
                      ? 'PID [direction] [pages] (e.g., "1234 down 3")'
                      : selectedAction === 'hotkey'
                      ? 'Keys (e.g., "cmd+c" or "ctrl+shift+esc")'
                      : 'Target'
                  }
                  className="flex-1 min-w-0 px-2 py-1.5 text-xs rounded-lg"
                  style={{
                    background: 'transparent',
                    border: '1px solid var(--color-border-subtle)',
                    color: 'var(--color-text)',
                  }}
                  onKeyDown={(e) => e.key === 'Enter' && selectedAction && runAction(selectedAction)}
                />
                <button
                  type="button"
                  className="text-xs px-2 py-1.5 rounded"
                  style={{
                    color: 'var(--color-cyan-light)',
                    border: '1px solid var(--color-border-subtle)',
                  }}
                  onClick={() => selectedAction && runAction(selectedAction)}
                  disabled={actionBusy || !targetInput.trim()}
                >
                  {actionBusy ? <Loader2 size={12} className="animate-spin" /> : 'Run'}
                </button>
                <button
                  type="button"
                  className="text-xs"
                  style={{ color: 'var(--color-text-muted)' }}
                  onClick={() => setSelectedAction(null)}
                >
                  Cancel
                </button>
              </div>
              {selectedAction && (
                <span className="text-xs" style={{ color: 'var(--color-text-faint)' }}>
                  {ACTIONS[selectedAction].description}
                </span>
              )}
            </div>
          )}

          {/* Result display */}
          {actionResult && (
            <div
              className="px-3 py-2 rounded-lg text-xs font-mono overflow-auto max-h-64"
              style={{
                background: actionResult.error ? 'rgba(248,113,113,0.1)' : 'rgba(16,185,129,0.1)',
                border: actionResult.error
                  ? '1px solid rgba(248,113,113,0.4)'
                  : '1px solid rgba(16,185,129,0.4)',
                color: actionResult.error ? '#fca5a5' : 'var(--color-emerald)',
              }}
            >
              <div className="flex items-center justify-between gap-2 mb-1">
                <span>
                  {actionResult.error ? <AlertTriangle size={12} /> : <Check size={12} />}
                  {actionResult.tool}
                </span>
                <button
                  type="button"
                  className="text-xs p-1"
                  style={{ color: 'var(--color-text-muted)' }}
                  onClick={() => setActionResult(null)}
                >
                  ✕
                </button>
              </div>
              <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {actionResult.error
                  ? actionResult.error
                  : JSON.stringify(actionResult.result, null, 2).slice(0, 3000)}
              </pre>
              {actionResult.result &&
                typeof actionResult.result === 'object' &&
                'screenshot' in actionResult.result && (
                <div className="mt-2">
                  <img
                    src={`data:image/png;base64,${actionResult.result.screenshot}`}
                    alt="Screenshot"
                    style={{ maxWidth: '100%', borderRadius: '4px', border: '1px solid var(--color-border-subtle)' }}
                  />
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}