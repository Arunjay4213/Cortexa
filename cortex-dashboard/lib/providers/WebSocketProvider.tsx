"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
} from "react";
import { useSWRConfig } from "swr";
import type { WebSocketMessage } from "@/lib/api/types";

interface WebSocketContextValue {
  connected: boolean;
  lastEvent: WebSocketMessage | null;
  lastSequenceId: number;
}

const WebSocketContext = createContext<WebSocketContextValue>({
  connected: false,
  lastEvent: null,
  lastSequenceId: 0,
});

export function useWebSocket() {
  return useContext(WebSocketContext);
}

const WS_BASE =
  process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/api/v1/ws";

export function WebSocketProvider({
  children,
  channel = "dashboard",
}: {
  children: React.ReactNode;
  channel?: string;
}) {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<WebSocketMessage | null>(null);
  const [lastSequenceId, setLastSequenceId] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const { mutate } = useSWRConfig();

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(`${WS_BASE}/${channel}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        reconnectAttempts.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WebSocketMessage;
          setLastEvent(data);

          // Check for sequence gaps
          if (
            lastSequenceId > 0 &&
            data.sequence_id > lastSequenceId + 1
          ) {
            // Gap detected — trigger full SWR revalidation
            mutate(() => true, undefined, { revalidate: true });
          }
          setLastSequenceId(data.sequence_id);

          // Targeted SWR cache invalidation based on event type
          if (data.type === "transaction") {
            mutate((key: string) =>
              typeof key === "string" &&
              (key.startsWith("/transactions") ||
                key.startsWith("/dashboard"))
            );
          } else if (data.type === "contradiction") {
            mutate((key: string) =>
              typeof key === "string" &&
              (key.startsWith("/health") || key.startsWith("/dashboard"))
            );
          } else if (data.type === "score") {
            mutate((key: string) =>
              typeof key === "string" && key.startsWith("/attribution")
            );
          } else if (data.type === "memory_update") {
            mutate((key: string) =>
              typeof key === "string" &&
              (key.startsWith("/memories") || key.startsWith("/dashboard"))
            );
          } else if (data.type === "transaction_created") {
            mutate((key: string) =>
              typeof key === "string" &&
              (key.startsWith("/transactions") || key.startsWith("/dashboard"))
            );
          } else if (data.type === "attribution_scored") {
            mutate((key: string) =>
              typeof key === "string" &&
              (key.startsWith("/attribution") || key.startsWith("/dashboard"))
            );
          } else if (data.type === "lifecycle_executed") {
            mutate((key: string) =>
              typeof key === "string" &&
              (key.startsWith("/lifecycle") || key.startsWith("/memories") || key.startsWith("/agents") || key.startsWith("/dashboard"))
            );
          } else if (data.type === "agent_updated") {
            mutate((key: string) =>
              typeof key === "string" &&
              (key.startsWith("/agents") || key.startsWith("/dashboard"))
            );
          }
        } catch {
          // Ignore non-JSON messages (like pong)
        }
      };

      ws.onclose = () => {
        setConnected(false);
        // Exponential backoff reconnect
        const delay = Math.min(
          1000 * Math.pow(2, reconnectAttempts.current),
          30000
        );
        reconnectAttempts.current++;
        reconnectTimeoutRef.current = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      // Connection failed, retry
      const delay = Math.min(
        1000 * Math.pow(2, reconnectAttempts.current),
        30000
      );
      reconnectAttempts.current++;
      reconnectTimeoutRef.current = setTimeout(connect, delay);
    }
  }, [channel, lastSequenceId, mutate]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connect]);

  return (
    <WebSocketContext.Provider value={{ connected, lastEvent, lastSequenceId }}>
      {children}
    </WebSocketContext.Provider>
  );
}
