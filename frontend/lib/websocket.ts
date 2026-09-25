/**
 * WebSocket streaming subscriber for real-time model token delivery.
 */

import { getEvalRun } from "@/lib/api";
import { useEvalStore } from "@/lib/store";

const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export function connectEvalWebSocket(runId: string): () => void {
  const wsUrl = `${WS_BASE_URL}/ws/eval/${runId}`;
  let socket: WebSocket | null = null;
  let isClosed = false;

  try {
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log(`[WebSocket] Connected to stream for run ${runId}`);
    };

    socket.onmessage = async (event) => {
      try {
        const data = JSON.parse(event.data);

        // Status update events (e.g. status="completed")
        if (data.status === "completed") {
          // Fetch complete scored evaluation results
          try {
            const finalResult = await getEvalRun(runId);
            useEvalStore.getState().setEvaluationComplete(
              finalResult.scores || [],
              finalResult.winner || null
            );
          } catch (err) {
            console.error("Failed to fetch final run scores:", err);
          }
          return;
        }

        // Token chunk events
        if (data.model_id) {
          if (!data.is_final) {
            if (data.token) {
              useEvalStore.getState().appendStreamToken(data.model_id, data.token);
            }
          } else {
            useEvalStore.getState().finalizeModelStream(
              data.model_id,
              data.output || "",
              data.latency_ms || 0,
              data.token_count || 0
            );
          }
        }
      } catch (err) {
        console.error("[WebSocket] Failed to parse message:", err);
      }
    };

    socket.onerror = (err) => {
      console.warn("[WebSocket] Stream error:", err);
    };

    socket.onclose = () => {
      if (!isClosed) {
        console.log(`[WebSocket] Connection closed for run ${runId}`);
      }
    };
  } catch (err) {
    console.error("[WebSocket] Connection initialization failed:", err);
    useEvalStore.getState().setError(String(err));
  }

  // Cleanup function to close socket when component unmounts
  return () => {
    isClosed = true;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.close();
    }
  };
}
