/**
 * Say what falls due this week, once, when the engine is up.
 *
 * Runs in the shell, not in a workspace, so it does not depend on the
 * person opening Memory — the whole point is that they need not. Desktop
 * only: the browser build has no notification service to speak through,
 * and the returning line on the landing already carries the count there.
 */
import { useEffect } from 'react';

import { desktop, isDesktop } from '@/desktop/desktop-bridge';
import { alreadySaid, dueSoonNotice, rememberSaid } from '@/lib/dueSoon';
import { fetchObligations } from '@/services/obligationsClient';
import { useSystemStore } from '@/stores/systemStore';

export function useDueSoon(): void {
  const online = useSystemStore((s) => s.backendOnline);

  useEffect(() => {
    if (!online || !isDesktop) return;
    let cancelled = false;
    (async () => {
      try {
        const listing = await fetchObligations();
        if (cancelled) return;
        const now = new Date();
        const storage = typeof localStorage === 'undefined' ? null : localStorage;
        const notice = dueSoonNotice(listing.obligations, now, alreadySaid(now, storage));
        if (!notice) return;
        await desktop.notify.show({ title: notice.title, body: notice.body });
        rememberSaid([...alreadySaid(now, storage), ...notice.ids], now, storage);
      } catch {
        /* nothing to say is the right outcome of a failed read */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [online]);
}
