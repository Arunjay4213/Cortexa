"use client";

import { useEffect, useRef } from "react";
import { useWebSocket } from "@/lib/providers/WebSocketProvider";
import { useToast } from "@/components/primitives/Toast";

/**
 * Bridges WebSocket events to toast notifications.
 * Renders nothing — pure side-effect component.
 */
export function WebSocketToastBridge() {
  const { lastEvent } = useWebSocket();
  const { addToast } = useToast();
  const lastIdRef = useRef<number>(0);

  useEffect(() => {
    if (!lastEvent) return;
    // Avoid duplicate toasts for the same event
    if (lastEvent.sequence_id <= lastIdRef.current) return;
    lastIdRef.current = lastEvent.sequence_id;

    switch (lastEvent.type) {
      case "transaction": {
        const d = lastEvent.data as any;
        addToast({
          type: "transaction",
          message: `New transaction ${d?.id?.slice(0, 8) ?? ""}`,
          detail: d?.query_text
            ? d.query_text.length > 80
              ? d.query_text.slice(0, 80) + "..."
              : d.query_text
            : undefined,
          link: d?.id ? `/attribution?selected=${d.id}` : "/attribution",
        });
        break;
      }
      case "contradiction": {
        const d = lastEvent.data as any;
        addToast({
          type: "contradiction",
          message: `Contradiction detected`,
          detail: d?.memory_id_1 && d?.memory_id_2
            ? `${d.memory_id_1.slice(0, 8)} \u2194 ${d.memory_id_2.slice(0, 8)}`
            : undefined,
          link: "/health",
        });
        break;
      }
      case "score": {
        const d = lastEvent.data as any;
        addToast({
          type: "score",
          message: `Attribution score updated`,
          detail: d?.memory_id
            ? `Memory ${d.memory_id.slice(0, 8)}`
            : undefined,
          link: d?.transaction_id
            ? `/attribution?selected=${d.transaction_id}`
            : "/attribution",
        });
        break;
      }
      default: {
        addToast({
          type: "info",
          message: `Event: ${lastEvent.type}`,
        });
      }
    }
  }, [lastEvent, addToast]);

  return null;
}
