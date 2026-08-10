/**
 * Listening — the parts that are invisible when they go wrong.
 *
 * The microphone track release is the one that matters most and is the easiest
 * to break: the browser's recording indicator is the only sight the user has of
 * Zaram listening, and a leaked track leaves it on after Zaram has stopped
 * caring. That is a privacy failure in a product whose claim is visibility, and
 * nothing in the UI would show it — which is exactly why it is asserted here
 * rather than trusted to a walkthrough.
 *
 * The second thing under test is the distinction between "Zaram cannot listen"
 * and "this attempt failed". A missing extra and a declined permission prompt
 * produce completely different advice, and collapsing them would tell someone
 * who clicked Block to go and download 81 MB.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useMicStore } from './micStore';

class FakeTrack {
  stopped = false;
  stop() {
    this.stopped = true;
  }
}

class FakeStream {
  tracks = [new FakeTrack(), new FakeTrack()];
  getTracks() {
    return this.tracks;
  }
}

let lastRecorder: FakeRecorder | null = null;
let lastStream: FakeStream | null = null;

class FakeRecorder {
  static supportedTypes = new Set(['audio/webm;codecs=opus']);
  static isTypeSupported(type: string) {
    return FakeRecorder.supportedTypes.has(type);
  }

  state: 'inactive' | 'recording' = 'inactive';
  mimeType: string;
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  /** Emitted on stop, as the real one does — the last chunk is flushed *before*
   *  `stop` fires, which is why the blob is assembled in the handler. */
  payload = 'spoken-audio';

  constructor(_stream: unknown, options?: { mimeType?: string }) {
    this.mimeType = options?.mimeType ?? '';
    lastRecorder = this;
  }

  start() {
    this.state = 'recording';
  }

  stop() {
    this.state = 'inactive';
    this.ondataavailable?.({ data: new Blob([this.payload]) });
    this.onstop?.();
  }
}

function stubBrowser({ deny = false }: { deny?: boolean } = {}) {
  vi.stubGlobal('MediaRecorder', FakeRecorder);
  vi.stubGlobal('navigator', {
    mediaDevices: {
      getUserMedia: vi.fn(async () => {
        if (deny) {
          const error = new Error('Permission denied');
          error.name = 'NotAllowedError';
          throw error;
        }
        lastStream = new FakeStream();
        return lastStream;
      }),
    },
  });
}

function stubFetch(response: Response | (() => Promise<Response>)) {
  const fn = typeof response === 'function' ? response : async () => response;
  const spy = vi.fn(fn);
  vi.stubGlobal('fetch', spy);
  return spy;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

beforeEach(() => {
  lastRecorder = null;
  lastStream = null;
  useMicStore.setState({ status: 'idle', unavailableReason: null, error: null });
});

afterEach(() => {
  useMicStore.getState().cancel();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('recording', () => {
  it('records with opus in webm when the browser supports it', async () => {
    stubBrowser();
    await useMicStore.getState().start();

    expect(useMicStore.getState().status).toBe('recording');
    expect(lastRecorder?.mimeType).toBe('audio/webm;codecs=opus');
  });

  it('falls back rather than refusing to record on an unfamiliar browser', async () => {
    stubBrowser();
    FakeRecorder.supportedTypes = new Set();
    try {
      await useMicStore.getState().start();
      expect(useMicStore.getState().status).toBe('recording');
    } finally {
      FakeRecorder.supportedTypes = new Set(['audio/webm;codecs=opus']);
    }
  });

  it('sends the recording to Zaram and returns what was heard', async () => {
    stubBrowser();
    const fetchSpy = stubFetch(json({ text: '  Send Harbour Lane the invoice.  ' }));

    await useMicStore.getState().start();
    const text = await useMicStore.getState().stop();

    expect(text).toBe('Send Harbour Lane the invoice.');
    const [url, init] = fetchSpy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/voice/transcribe');
    expect(init.method).toBe('POST');
    // The content type has to be the one the recording was actually made in;
    // the backend hands the bytes straight to a decoder that believes it.
    expect((init.headers as Record<string, string>)['Content-Type']).toBe(
      'audio/webm;codecs=opus',
    );
  });
});

describe('the microphone is released', () => {
  it('after a successful transcription', async () => {
    stubBrowser();
    stubFetch(json({ text: 'hello' }));

    await useMicStore.getState().start();
    const stream = lastStream!;
    await useMicStore.getState().stop();

    expect(stream.getTracks().every((t) => t.stopped)).toBe(true);
  });

  it('after a failed transcription', async () => {
    stubBrowser();
    stubFetch(async () => {
      throw new Error('backend is down');
    });

    await useMicStore.getState().start();
    const stream = lastStream!;
    await useMicStore.getState().stop();

    expect(stream.getTracks().every((t) => t.stopped)).toBe(true);
    expect(useMicStore.getState().error).toBe('backend is down');
  });

  it('when the recording is cancelled without being sent', async () => {
    stubBrowser();
    await useMicStore.getState().start();
    const stream = lastStream!;

    useMicStore.getState().cancel();

    expect(stream.getTracks().every((t) => t.stopped)).toBe(true);
    expect(useMicStore.getState().status).toBe('idle');
  });
});

describe('what went wrong, and whose problem it is', () => {
  it('a declined permission prompt is an error, not a missing capability', async () => {
    stubBrowser({ deny: true });

    await useMicStore.getState().start();

    expect(useMicStore.getState().error).toBe(
      'Zaram was not given access to the microphone.',
    );
    // Telling someone who clicked Block to install 81 MB would be a wrong
    // diagnosis rendered confidently.
    expect(useMicStore.getState().unavailableReason).toBeNull();
    expect(useMicStore.getState().status).toBe('idle');
  });

  it('a 503 disables the control and carries the backend’s own reason', async () => {
    stubBrowser();
    stubFetch(
      json(
        { detail: 'Listening needs the mic extra: pip install zaram[mic] (81 MB, one time)' },
        503,
      ),
    );

    await useMicStore.getState().start();
    const text = await useMicStore.getState().stop();

    expect(text).toBe('');
    // The reason names the install and its size. It is shown as written, so the
    // user can act on it rather than being told "unavailable".
    expect(useMicStore.getState().unavailableReason).toContain('zaram[mic]');
    expect(useMicStore.getState().unavailableReason).toContain('81 MB');
    expect(useMicStore.getState().error).toBeNull();
  });

  it('checkAvailability reports why listening is off', async () => {
    stubBrowser();
    stubFetch(json({ available: false, reason: 'weights are not on this machine' }));

    await useMicStore.getState().checkAvailability();

    expect(useMicStore.getState().unavailableReason).toBe(
      'weights are not on this machine',
    );
  });

  it('checkAvailability clears the reason once listening works', async () => {
    stubBrowser();
    useMicStore.setState({ unavailableReason: 'stale' });
    stubFetch(json({ available: true }));

    await useMicStore.getState().checkAvailability();

    expect(useMicStore.getState().unavailableReason).toBeNull();
  });

  it('a browser that cannot record says so instead of failing on press', async () => {
    vi.stubGlobal('MediaRecorder', undefined);
    vi.stubGlobal('navigator', {});

    await useMicStore.getState().checkAvailability();

    expect(useMicStore.getState().unavailableReason).toBe(
      'This browser cannot record audio.',
    );
  });

  it('an empty recording is not sent anywhere', async () => {
    stubBrowser();
    const fetchSpy = stubFetch(json({ text: 'should not be reached' }));

    await useMicStore.getState().start();
    lastRecorder!.payload = '';
    const text = await useMicStore.getState().stop();

    expect(text).toBe('');
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
