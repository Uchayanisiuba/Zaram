/**
 * The region where source panels appear — over the orb, beside the conversation.
 *
 * Rendered at app level rather than inside the conversation panel, because the
 * panels sit in the orb's space and the orb has to recede while they are open.
 * Neither surface could own that state alone.
 *
 * Placement is a fixed cascade rather than scattered. Free-floating windows
 * become clutter after about four and make window management the user's job,
 * which is against "calm over delight" and a non-technical target user. A
 * predictable stack keeps several sources readable and their positions
 * learnable.
 */
import { AnimatePresence } from 'framer-motion';
import { useSourceStore, cascadeOffset } from '@/stores/sourceStore';
import { useLayoutStore } from '@/stores/layoutStore';
import { useChatModeStore } from '@/stores/chatModeStore';
import SourcePanel from './SourcePanel';

export default function SourcePanelLayer() {
  const open = useSourceStore((s) => s.open);
  const closeSource = useSourceStore((s) => s.closeSource);
  const markForgotten = useSourceStore((s) => s.markForgotten);
  const chatFraction = useLayoutStore((s) => s.chatFraction);
  const chatOpen = useChatModeStore((s) => s.chatView) === 'chat';

  if (open.length === 0) return null;

  // Occupy the space the conversation panel leaves, which is where the orb is.
  const rightInset = chatOpen ? `${chatFraction * 100}%` : '0%';

  return (
    <div
      className="fixed inset-y-0 left-0 z-[70] pointer-events-none"
      style={{ right: rightInset }}
    >
      <AnimatePresence>
        {open.map((source, i) => (
          <SourcePanel
            key={source.url}
            url={source.url}
            offset={cascadeOffset(i)}
            // The most recently opened panel sits on top.
            depth={i}
            returnFocusTo={source.origin}
            onClose={() => closeSource(source.url)}
            onDeleted={() => {
              markForgotten(source.url);
              closeSource(source.url);
            }}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}
