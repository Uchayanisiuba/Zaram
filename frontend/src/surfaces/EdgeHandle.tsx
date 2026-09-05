/**
 * The screen-edge handle.
 *
 * A thin strip against the right edge, over whatever the user is working in.
 * Hovering widens it; clicking summons the panel. That is the entire surface,
 * and the restraint is the design — the handle competes with nothing because
 * it is six pixels wide until it is approached.
 *
 * **The hover is reported, not observed.** The main process could learn where
 * the cursor is by polling `screen.getCursorScreenPoint`, and that would be a
 * watcher: a timer running all day, reading the user's pointer, whether or not
 * they ever come near Zaram. A pointer entering *this window* is a browser
 * event about this window, and it is the only thing reported. `CLAUDE.md`:
 * invoked, never passive.
 */
import { useCallback, useState } from 'react';

export default function EdgeHandle() {
  const [hovered, setHovered] = useState(false);

  const report = useCallback((next: boolean) => {
    setHovered(next);
    void window.zaram?.ambient?.hover(next);
  }, []);

  return (
    <button
      type="button"
      className={`edge-handle${hovered ? ' edge-handle--hovered' : ''}`}
      data-testid="edge-handle"
      aria-label="Open Zaram"
      title="Open Zaram"
      onPointerEnter={() => report(true)}
      onPointerLeave={() => report(false)}
      onClick={() => void window.zaram?.ambient?.summon()}
    >
      <span className="edge-handle__grip" aria-hidden="true" />
    </button>
  );
}
