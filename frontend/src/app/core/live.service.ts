import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { LiveEvent } from './api.service';

/**
 * Parse a raw WebSocket frame into an xwa-sdk `Event` envelope.
 * Returns `null` for malformed JSON or envelopes missing the mandatory fields
 * (`seq`, `type`, `analysis_id`).
 */
export function parseLiveEvent(raw: unknown): LiveEvent | null {
  if (typeof raw !== 'string') {
    return null;
  }

  let parsed: Partial<LiveEvent>;
  try {
    parsed = JSON.parse(raw) as Partial<LiveEvent>;
  } catch {
    return null;
  }

  if (
    !parsed ||
    typeof parsed.seq !== 'number' ||
    typeof parsed.type !== 'string' ||
    !parsed.type ||
    typeof parsed.analysis_id !== 'string' ||
    !parsed.analysis_id
  ) {
    return null;
  }

  return {
    seq: parsed.seq,
    type: parsed.type,
    tool: typeof parsed.tool === 'string' ? parsed.tool : '',
    analysis_id: parsed.analysis_id,
    ts: typeof parsed.ts === 'string' ? parsed.ts : '',
    payload: parsed.payload ?? null,
  };
}

/**
 * Thin WebSocket wrapper that exposes xwa-sdk `Event` envelopes as an
 * Observable. Errors emitted by the server arrive as ``analysis_error`` events;
 * transport errors are surfaced through the Observable error channel.
 */
@Injectable({ providedIn: 'root' })
export class LiveService {
  connect(url: string): Observable<LiveEvent> {
    return new Observable<LiveEvent>((subscriber) => {
      const socket = new WebSocket(url);

      socket.onmessage = (message) => {
        const event = parseLiveEvent(message.data);
        if (event) {
          subscriber.next(event);
        }
      };

      socket.onerror = () => {
        subscriber.error(new Error('WebSocket transport error'));
      };

      socket.onclose = (event) => {
        if (event.wasClean) {
          subscriber.complete();
        } else {
          subscriber.error(new Error(`WebSocket closed with code ${event.code}`));
        }
      };

      return () => {
        if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
          socket.close(1000, 'client closed');
        }
      };
    });
  }
}
