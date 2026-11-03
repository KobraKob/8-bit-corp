import { useAppStore } from './useAppStore';

function trimTrailingSlashes(value: string): string {
  let end = value.length;
  while (end > 0 && value[end - 1] === '/') end -= 1;
  return value.slice(0, end);
}

const apiBase = trimTrailingSlashes(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api');
const apiRoot = apiBase.endsWith('/api') ? apiBase.slice(0, -4) : apiBase;
const defaultSocketUrl = apiRoot.startsWith('https://')
  ? 'wss://' + apiRoot.slice('https://'.length) + '/ws'
  : 'ws://' + apiRoot.slice('http://'.length) + '/ws';

class WebSocketClient {
  private ws: WebSocket | null = null;
  private url = import.meta.env.VITE_WS_URL || defaultSocketUrl;
  private reconnectInterval = 1000;
  private readonly maxReconnectInterval = 10000;
  private isConnecting = false;
  private shouldReconnect = true;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  connect() {
    this.shouldReconnect = true;
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      useAppStore.getState().setNetworkStatus('offline');
      return;
    }
    if (this.isConnecting || (this.ws && this.ws.readyState <= WebSocket.OPEN)) return;

    this.clearReconnectTimer();
    this.isConnecting = true;
    try {
      const socket = new WebSocket(this.url);
      this.ws = socket;
      socket.onopen = () => {
        this.isConnecting = false;
        this.reconnectInterval = 1000;
        useAppStore.getState().setNetworkStatus('connected');
        const { lastEventId, activeProjectId } = useAppStore.getState();
        socket.send(JSON.stringify({
          type: 'resume',
          last_event_id: lastEventId,
          project_id: activeProjectId,
        }));
      };
      socket.onmessage = (event) => {
        try {
          useAppStore.getState().handleIncomingEvent(JSON.parse(event.data));
        } catch (error) {
          console.error('[Pixel Corp] Could not process live event:', error);
        }
      };
      socket.onclose = () => {
        if (this.ws === socket) this.ws = null;
        this.isConnecting = false;
        if (!this.shouldReconnect) return;
        useAppStore.getState().setNetworkStatus(
          typeof navigator !== 'undefined' && !navigator.onLine ? 'offline' : 'degraded'
        );
        this.scheduleReconnect();
      };
      socket.onerror = () => socket.close();
    } catch (error) {
      this.isConnecting = false;
      if (this.shouldReconnect) {
        useAppStore.getState().setNetworkStatus('degraded');
        this.scheduleReconnect();
      }
    }
  }

  private clearReconnectTimer() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private scheduleReconnect() {
    if (!this.shouldReconnect || this.reconnectTimer || (typeof navigator !== 'undefined' && !navigator.onLine)) return;
    const delay = this.reconnectInterval;
    this.reconnectInterval = Math.min(Math.round(this.reconnectInterval * 1.7), this.maxReconnectInterval);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  disconnect() {
    this.shouldReconnect = false;
    this.clearReconnectTimer();
    const socket = this.ws;
    this.ws = null;
    this.isConnecting = false;
    socket?.close();
  }
}

export const wsClient = new WebSocketClient();
