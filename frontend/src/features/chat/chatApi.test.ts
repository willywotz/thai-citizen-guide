import { http, HttpResponse } from 'msw';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { server } from '@/mocks/server';
import { STREAM_IDLE_TIMEOUT_MS } from '@/shared/constants/query';

import { sendChatQuerySSE } from './chatApi';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function sseChunk(event: string, data: unknown): Uint8Array {
  const text = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
  return new TextEncoder().encode(text);
}

/**
 * Returns an MSW handler for POST /api/v1/chat/stream that:
 * 1. Immediately enqueues `initialChunk` into the stream.
 * 2. Never closes the stream (simulating a hung server).
 *
 * The returned `streamController` lets you manually close the stream in tests.
 */
function makeHangingSSEHandler(initialChunk: Uint8Array): {
  handler: ReturnType<typeof http.post>;
  closeStream: () => void;
} {
  let streamController: ReadableStreamDefaultController<Uint8Array> | null = null;

  const handler = http.post('*/api/v1/chat/stream', () => {
    const stream = new ReadableStream<Uint8Array>({
      start(c) {
        streamController = c;
        c.enqueue(initialChunk);
        // Do NOT call c.close() — hang forever
      },
    });

    return new HttpResponse(stream, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    });
  });

  return {
    handler,
    closeStream: () => streamController?.close(),
  };
}

/**
 * Returns an MSW handler for POST /api/v1/chat/stream that emits one step
 * event and then immediately closes the stream (normal happy path).
 */
function makeCompletingSSEHandler(): ReturnType<typeof http.post> {
  return http.post('*/api/v1/chat/stream', () => {
    const stream = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(sseChunk('step', { step: 'thinking' }));
        c.enqueue(sseChunk('done', { sessionId: 'sess-1', answer: 'Hello!' }));
        c.close();
      },
    });

    return new HttpResponse(stream, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    });
  });
}

// ---------------------------------------------------------------------------
// SSE idle timeout (Task 4)
// ---------------------------------------------------------------------------

describe('sendChatQuerySSE — idle timeout', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('RED → GREEN: fires connection-lost (onError) when stream hangs past STREAM_IDLE_TIMEOUT_MS', async () => {
    const { handler } = makeHangingSSEHandler(
      sseChunk('step', { step: 'thinking' }),
    );
    server.use(handler);

    const onError = vi.fn();
    const onStep = vi.fn();

    const promise = sendChatQuerySSE(
      { query: 'test' },
      { onStep, onError },
    );

    // Let the first step event arrive (flush microtasks/promises)
    await vi.advanceTimersByTimeAsync(0);

    // Advance past the idle timeout
    await vi.advanceTimersByTimeAsync(STREAM_IDLE_TIMEOUT_MS + 1);

    await promise;

    // The step event was received before the hang
    expect(onStep).toHaveBeenCalledTimes(1);
    // After timeout, the connection-lost path fires via onError
    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ message: expect.any(String) }),
    );
  });

  it('does NOT fire onError when stream completes normally within the timeout', async () => {
    server.use(makeCompletingSSEHandler());

    const onError = vi.fn();
    const onStep = vi.fn();
    const onDone = vi.fn();

    const promise = sendChatQuerySSE(
      { query: 'test' },
      { onStep, onError, onDone },
    );

    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(STREAM_IDLE_TIMEOUT_MS - 1000);

    await promise;

    expect(onStep).toHaveBeenCalledTimes(1);
    expect(onDone).toHaveBeenCalledTimes(1);
    expect(onError).not.toHaveBeenCalled();
  });
});
