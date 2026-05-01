import { useState, useCallback } from "react";
import { createSSEConnection } from "../api/client.js";

export function useSSE() {
  const [events, setEvents] = useState([]);
  const [isComplete, setIsComplete] = useState(false);
  const [finalResponse, setFinalResponse] = useState(null);
  const [error, setError] = useState(null);

  const listen = useCallback((sessionId, taskId, onComplete) => {
    setEvents([]);
    setIsComplete(false);
    setFinalResponse(null);
    setError(null);

    const cleanup = createSSEConnection(sessionId, taskId, {
      onNodeComplete: (payload) => {
        setEvents((prev) => [...prev, payload]);
      },
      onDone: (payload) => {
        setFinalResponse(payload.final_response || "Done.");
        setIsComplete(true);
        onComplete?.();
      },
      onError: (payload) => {
        setError(payload.error || "Unknown error");
        setIsComplete(true);
        onComplete?.();
      },
    });

    return cleanup;
  }, []);

  return { events, isComplete, finalResponse, error, listen };
}
