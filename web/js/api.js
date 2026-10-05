/**
 * web/js/api.js
 * Client API helper for fetching registry, metrics, and managing WebSocket connections.
 */

export async function fetchRegistry() {
  const res = await fetch("/api/registry");
  if (!res.ok) throw new Error(`Failed to fetch registry: ${res.statusText}`);
  return await res.json();
}

export async function fetchMetrics() {
  const res = await fetch("/api/metrics");
  if (!res.ok) throw new Error(`Failed to fetch metrics: ${res.statusText}`);
  return await res.json();
}

export class WSClient {
  constructor(onMessage, onError, onClose) {
    this.onMessage = onMessage;
    this.onError = onError;
    this.onClose = onClose;
    this.ws = null;
  }

  connect() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (this.onMessage) this.onMessage(msg);
      } catch (e) {
        console.error("Failed to parse WS JSON:", e);
      }
    };

    this.ws.onerror = (err) => {
      if (this.onError) this.onError(err);
    };

    this.ws.onclose = () => {
      if (this.onClose) this.onClose();
    };
  }

  send(payload) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
    } else {
      console.warn("WebSocket is not connected.");
    }
  }

  close() {
    if (this.ws) {
      this.ws.close();
    }
  }
}
