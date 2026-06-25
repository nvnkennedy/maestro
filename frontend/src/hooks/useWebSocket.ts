import { useEffect } from 'react';
import { maestroSocket } from '../services/websocket';
import type { WsEvent } from '../types/domain';

/** Subscribe to live execution events for the lifetime of the component. */
export function useWebSocket(onEvent: (event: WsEvent) => void): void {
  useEffect(() => {
    const unsubscribe = maestroSocket.subscribe(onEvent);
    return unsubscribe;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
