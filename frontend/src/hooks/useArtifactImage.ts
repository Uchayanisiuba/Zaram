/**
 * An object URL for an artifact whose file is a picture.
 *
 * Why a hook rather than an `<img src>`
 * -------------------------------------
 * The backend authenticates every request against this launch's credential,
 * and that credential is attached by a wrapper around `fetch`. An `<img>` does
 * not fetch — it loads a subresource, with no way to set a header — so
 * pointing one at `/artifacts/<id>/download` gets a 401 and renders a broken
 * image. Same reason the download button stopped being an anchor.
 *
 * So the bytes are fetched, wrapped in an object URL, and released when the
 * component goes away. The release is the part worth being careful about: an
 * object URL that is never revoked is a copy of the file held in memory for
 * the life of the tab, and a grid of four 1024x1024 PNGs is several megabytes
 * of that per request.
 */
import { useEffect, useState } from 'react';

import { artifactImageUrl } from '@/services/artifactsClient';

export interface ArtifactImage {
  /** Object URL, or `null` while loading or after a failure. */
  url: string | null;
  /** Why it could not be shown. `null` while loading and on success. */
  error: string | null;
  loading: boolean;
}

export function useArtifactImage(id: string, enabled = true): ArtifactImage {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(enabled);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    // Held in a local rather than read back out of state on cleanup: state is
    // stale in a cleanup closure, and the URL this effect created is the one
    // this effect has to release.
    let created: string | null = null;

    setLoading(true);
    setError(null);

    artifactImageUrl(id)
      .then((objectUrl) => {
        created = objectUrl;
        if (cancelled) {
          // Unmounted while the fetch was in flight. Nothing will render it,
          // so it is released here rather than leaked.
          URL.revokeObjectURL(objectUrl);
          return;
        }
        setUrl(objectUrl);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Could not load that image.');
        setLoading(false);
      });

    return () => {
      cancelled = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [id, enabled]);

  return { url, error, loading };
}
