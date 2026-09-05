/**
 * Knowledge domains — transport.
 *
 * Field names are the backend's, for the reason `artifactsClient.ts` gives: a
 * mapping layer is a second vocabulary and a place for the two to disagree
 * quietly.
 *
 * A refusal carries the backend's own sentence. "A domain needs a line saying
 * what is in it" is something a person can act on; `400` is not.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

export interface KnowledgeDomain {
  id: string;
  name: string;
  /** Required, and load-bearing: routing reads it to decide when to reach for
   *  this domain, and a reply quotes it back when it does. */
  description: string;
  created_at: number;
  updated_at: number;
  /** The sources in this domain. Many-to-many — a source can be in several. */
  source_ids: string[];
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    let detail = '';
    try {
      detail = ((await response.json()) as { detail?: string }).detail ?? '';
    } catch {
      /* not every failure has a body */
    }
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

const asJson = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export async function fetchDomains(): Promise<KnowledgeDomain[]> {
  const data = await json<{ domains: KnowledgeDomain[] }>('/knowledge/domains');
  return data.domains;
}

export async function createDomain(
  name: string,
  description: string,
): Promise<KnowledgeDomain> {
  return json<KnowledgeDomain>('/knowledge/domains', asJson({ name, description }));
}

export async function renameDomain(
  id: string,
  name: string,
  description: string,
): Promise<KnowledgeDomain> {
  return json<KnowledgeDomain>(`/knowledge/domains/${id}`, {
    ...asJson({ name, description }),
    method: 'PUT',
  });
}

/** Removes the domain only. Its sources and their facts are untouched — one
 *  memory, many domains. */
export async function deleteDomain(id: string): Promise<void> {
  await json(`/knowledge/domains/${id}`, { method: 'DELETE' });
}

export async function addSourceToDomain(
  domainId: string,
  sourceId: string,
): Promise<KnowledgeDomain> {
  return json<KnowledgeDomain>(`/knowledge/domains/${domainId}/sources/${sourceId}`, {
    method: 'POST',
  });
}

export async function removeSourceFromDomain(
  domainId: string,
  sourceId: string,
): Promise<KnowledgeDomain> {
  return json<KnowledgeDomain>(`/knowledge/domains/${domainId}/sources/${sourceId}`, {
    method: 'DELETE',
  });
}
