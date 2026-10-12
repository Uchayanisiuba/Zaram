/**
 * @vitest-environment jsdom
 *
 * Photographs are asked for once per description, a second caller waits for
 * the answer already on its way, a refusal is kept until the person asks again,
 * and an unreachable backend is not recorded as a reason.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { usePhotoStore } from './photoStore';

const fetchMock = vi.fn();

beforeEach(() => {
  usePhotoStore.setState({ found: {} });
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});

const answer = (results: object[]) => new Response(JSON.stringify({ results }), { status: 200 });

const found = (description: string) => ({
  description,
  data_uri: 'data:image/jpeg;base64,eA==',
  title: 'T',
  creator: 'C',
  license_label: 'CC BY 2.0',
  license_url: 'https://creativecommons.org/licenses/by/2.0/',
  source_url: 'https://example.org/p',
});

describe('looking up a page’s photographs', () => {
  it('sends the descriptions and the person’s request, inline, and keeps what came back', async () => {
    fetchMock.mockResolvedValue(answer([found('Lagos beach'), { description: 'old town', error: 'No match.', code: 'no_match' }]));
    await usePhotoStore.getState().ensure(['Lagos beach', 'old town'], 'a tourism site for Lagos');
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/photos\/find$/);
    expect(JSON.parse(init.body)).toEqual({
      descriptions: ['Lagos beach', 'old town'],
      request: 'a tourism site for Lagos',
      inline: true,
    });
    const state = usePhotoStore.getState().found;
    expect(state['lagos beach']).toMatchObject({ uri: 'data:image/jpeg;base64,eA==', license: 'CC BY 2.0' });
    expect(state['old town']).toEqual({ error: 'No match.', code: 'no_match' });
  });

  it('keeps the source each photo came from, so it can be credited', async () => {
    fetchMock.mockResolvedValue(
      answer([
        { ...found('Lagos beach'), source: 'Openverse' },
        { ...found('old town'), source: 'Wikimedia Commons' },
      ]),
    );
    await usePhotoStore.getState().ensure(['Lagos beach', 'old town'], '');
    const state = usePhotoStore.getState().found;
    expect(state['lagos beach']).toMatchObject({ source: 'Openverse' });
    expect(state['old town']).toMatchObject({ source: 'Wikimedia Commons' });
  });

  it('looks again for photos left over when the time budget ran out', async () => {
    fetchMock.mockResolvedValueOnce(answer([{ description: 'beach', error: 'Stopped after 60 seconds.', code: 'busy' }]));
    await usePhotoStore.getState().ensure(['beach'], '');
    fetchMock.mockResolvedValueOnce(answer([found('beach')]));
    await usePhotoStore.getState().lookAgain(['beach'], '');
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(usePhotoStore.getState().found.beach).toHaveProperty('uri');
  });

  it('asks once, and a second caller waits for that answer', async () => {
    let release!: (r: Response) => void;
    fetchMock.mockReturnValue(new Promise<Response>((r) => (release = r)));
    const first = usePhotoStore.getState().ensure(['beach'], '');
    let secondDone = false;
    const second = usePhotoStore.getState().ensure(['Beach'], '').then(() => (secondDone = true));
    await Promise.resolve();
    expect(secondDone).toBe(false);
    release(answer([found('beach')]));
    await Promise.all([first, second]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(usePhotoStore.getState().found.beach).toBeTruthy();
  });

  it('keeps a refusal, and looks again only when asked to', async () => {
    fetchMock.mockResolvedValueOnce(answer([{ description: 'beach', error: 'You chose not to.', code: 'consent_declined' }]));
    await usePhotoStore.getState().ensure(['beach'], '');
    await usePhotoStore.getState().ensure(['beach'], '');
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fetchMock.mockResolvedValueOnce(answer([found('beach')]));
    await usePhotoStore.getState().lookAgain(['beach'], '');
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(usePhotoStore.getState().found.beach).toHaveProperty('uri');
  });

  it('does not look again for "nothing matched"', async () => {
    usePhotoStore.setState({ found: { beach: { error: 'No match.', code: 'no_match' } } });
    await usePhotoStore.getState().lookAgain(['beach'], '');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('leaves a description unsettled when the backend cannot be reached', async () => {
    fetchMock.mockRejectedValueOnce(new Error('down'));
    await usePhotoStore.getState().ensure(['beach'], '');
    expect(usePhotoStore.getState().found).toEqual({});
    fetchMock.mockResolvedValueOnce(answer([found('beach')]));
    await usePhotoStore.getState().ensure(['beach'], '');
    expect(usePhotoStore.getState().found.beach).toHaveProperty('uri');
  });
});
