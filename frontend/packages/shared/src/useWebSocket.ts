import { useEffect, useRef, useCallback, useState } from "react";

interface InventoryUpdate {
  type: "inventory_updated";
  inventory_item_id: number;
  location_id: number;
  available: number;
}

export function useWebSocket(onInventoryUpdate: (update: InventoryUpdate) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const callbackRef = useRef(onInventoryUpdate);
  callbackRef.current = onInventoryUpdate;
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    const connect = () => {
      if (cancelled) return;
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${protocol}//${window.location.host}/api/ws`);

      ws.onopen = () => { if (!cancelled) setConnected(true); };
      ws.onclose = () => {
        if (!cancelled) {
          setConnected(false);
          reconnectTimer = setTimeout(connect, 3000);
        }
      };
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data) as InventoryUpdate;
        if (data.type === "inventory_updated") {
          callbackRef.current(data);
        }
      };

      wsRef.current = ws;
    };

    connect();

    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, []);

  return { connected };
}
