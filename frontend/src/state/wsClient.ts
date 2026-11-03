import { useAppStore } from './useAppStore';

const apiBase = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api').replace(/\/+$/, '');
const defaultSocketUrl = apiBase.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:').replace(/\/api$/, '') + '/ws';

class WebSocketClient {
  private ws: WebSocket | null = null;
  private url = import.meta.env.VITE_WS_URL || defaultSocketUrl;
  private reconnectInterval = 1000;
  private maxReconnectInterval = 10000;
  private isConnecting = false;
  private shouldReconnect = true;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  connect() {
    this.shouldReconnect = true;
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) return;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.isConnecting = true;
    try {
      this.ws = new WebSocket(this.url);
      this.ws.onopen = () => {
        this.isConnecting = false;
        this.reconnectInterval = 1000;
        const { lastEventId, activeProjectId } = useAppStore.getState();
        this.ws?.send(JSON.stringify({ type: 'resume', last_event_id: lastEventId, project_id: activeProjectId }));
      };
      this.ws.onmessage = (event) => {
        try {
          useAppStore.getState().handleIncomingEvent(JSON.parse(event.data));
        } catch (error) {
          console.error('[PixelCorp WS] Failed to process event:', error);
        }
      };
      this.ws.onclose = () => {
        this.isConnecting = false;
        this.ws = null;
        this.scheduleReconnect();
      };
      this.ws.onerror = () => this.ws?.close();
    } catch (error) {
      console.error('[PixelCorp WS] Connection attempt failed:', error);
      this.isConnecting = false;
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect() {
    if (!this.shouldReconnect || this.reconnectTimer) return;
    const delay = this.reconnectInterval;
    this.reconnectInterval = Math.min(this.reconnectInterval * 1.5, this.maxReconnectInterval);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  disconnect() {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
    this.isConnecting = false;
  }
}

export const wsClient = new WebSocketClient();
