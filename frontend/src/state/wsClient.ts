import { useAppStore } from './useAppStore';
import { API_WS_URL } from '../api/client';

class WebSocketClient {
  private ws: WebSocket | null = null;
  private url = API_WS_URL;
  private shouldReconnect = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectInterval = 1000;
  private maxReconnectInterval = 10000;
  private isConnecting = false;

  connect() {
    this.shouldReconnect = true;
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) return;

    this.isConnecting = true;
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('[PixelCorp WS] Connected.');
        this.isConnecting = false;
        this.reconnectInterval = 1000;

        // Send resume with last_event_id for seamless catch-up
        const lastId = useAppStore.getState().lastEventId;
        const activeProj = useAppStore.getState().activeProjectId;
        this.ws?.send(
          JSON.stringify({
            type: 'resume',
            last_event_id: lastId,
            project_id: activeProj,
          })
        );
      };

      this.ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          useAppStore.getState().handleIncomingEvent(payload);
        } catch (e) {
          console.error('[PixelCorp WS] Error parsing event message:', e);
        }
      };

      this.ws.onclose = () => {
        console.warn('[PixelCorp WS] Disconnected. Reconnecting in', this.reconnectInterval, 'ms...');
        this.isConnecting = false;
        this.ws = null;
        if (this.shouldReconnect) {
          this.reconnectTimer = setTimeout(() => this.connect(), this.reconnectInterval);
          this.reconnectInterval = Math.min(this.reconnectInterval * 1.5, this.maxReconnectInterval);
        }
      };

      this.ws.onerror = (err) => {
        console.error('[PixelCorp WS] Socket error:', err);
        this.ws?.close();
      };
    } catch (err) {
      console.error('[PixelCorp WS] Connection attempt failed:', err);
      this.isConnecting = false;
      if (this.shouldReconnect) {
        this.reconnectTimer = setTimeout(() => this.connect(), this.reconnectInterval);
      }
    }
  }

  disconnect() {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export const wsClient = new WebSocketClient();
