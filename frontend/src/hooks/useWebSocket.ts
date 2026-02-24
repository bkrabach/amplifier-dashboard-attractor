/**
 * useWebSocket -- connects to the backend WebSocket for live pipeline updates.
 *
 * Auto-reconnects on disconnect with exponential backoff.
 * Returns the latest state snapshot and connection status.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import type { PipelineRunState } from "../lib/types";

const WS_BASE = "/ws";
const INITIAL_RETRY_MS = 1000;
const MAX_RETRY_MS = 16000;

export interface UseWebSocketResult {
  state: PipelineRunState | null;
  connected: boolean;
}

export function useWebSocket(contextId: string | undefined): UseWebSocketResult {
  const [state, setState] = useState<PipelineRunState | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retryMs = useRef(INITIAL_RETRY_MS);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmounted = useRef(false);

  const connect = useCallback(() => {
    if (!contextId || unmounted.current) return;

    // Determine WebSocket URL — works with Vite proxy in dev
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${window.location.host}${WS_BASE}/pipelines/${contextId}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (unmounted.current) { ws.close(); return; }
      setConnected(true);
      retryMs.current = INITIAL_RETRY_MS;
    };

    ws.onmessage = (event) => {
      if (unmounted.current) return;
      try {
        const data = JSON.parse(event.data) as PipelineRunState;
        setState(data);
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      if (unmounted.current) return;
      setConnected(false);
      // Exponential backoff reconnect
      retryTimer.current = setTimeout(() => {
        retryMs.current = Math.min(retryMs.current * 2, MAX_RETRY_MS);
        connect();
      }, retryMs.current);
    };

    ws.onerror = () => {
      // onclose will fire after onerror, triggering reconnect
    };
  }, [contextId]);

  useEffect(() => {
    unmounted.current = false;
    connect();

    return () => {
      unmounted.current = true;
      if (retryTimer.current) clearTimeout(retryTimer.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return { state, connected };
}
