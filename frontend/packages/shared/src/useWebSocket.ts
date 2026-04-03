import { useEffect, useRef, useCallback, useState } from "react";

interface InventoryUpdate {
  type: "inventory_updated";
  inventory_item_id: number;
  location_id: number;
  available: number;
}

export function useWebSocket(onInventoryUpdate: (update: InventoryUpdate) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/ws`);

    ws.onopen = () => setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      setTimeout(connect, 3000);
    };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data) as InventoryUpdate;
      if (data.type === "inventory_updated") {
        onInventoryUpdate(data);
      }
    };

    wsRef.current = ws;
  }, [onInventoryUpdate]);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  return { connected };
}
