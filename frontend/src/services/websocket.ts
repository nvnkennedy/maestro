import type { WsEvent } from '../types/domain';
import { apiToken } from './api';

type Listener = (event: WsEvent) => void;

/** Singleton auto-reconnecting WebSocket client for execution events. */
class MaestroSocket {
  private socket: WebSocket | null = null;
  private listeners = new Set<Listener>();
  private reconnectDelay = 1000;

  connect(): void {
    if (this.socket && this.socket.readyState <= WebSocket.OPEN) return;
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    // Browsers can't set WS headers, so the token rides as a query param.
    const auth = apiToken ? `?token=${encodeURIComponent(apiToken)}` : '';
    this.socket = new WebSocket(`${protocol}://${window.location.host}/ws${auth}`);
    this.socket.onopen = () => {
      this.reconnectDelay = 1000;
    };
    this.socket.onmessage = (message) => {
      try {
        const event: WsEvent = JSON.parse(message.data);
        this.listeners.forEach((listener) => listener(event));
      } catch {
        /* ignore malformed frames */
      }
    };
    this.socket.onclose = () => {
      this.socket = null;
      setTimeout(() => this.connect(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 15000);
    };
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    this.connect();
    return () => this.listeners.delete(listener);
  }
}

export const maestroSocket = new MaestroSocket();
