const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

export async function createSession() {
  const res = await fetch(`${BASE_URL}/session/`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to create session: ${res.status}`);
  return res.json();
}

export async function submitTask(sessionId, task) {
  const res = await fetch(`${BASE_URL}/session/${sessionId}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task }),
  });
  if (!res.ok) throw new Error(`Failed to submit task: ${res.status}`);
  return res.json();
}

export async function getHistory(sessionId) {
  const res = await fetch(`${BASE_URL}/session/${sessionId}/history`);
  if (!res.ok) throw new Error(`Failed to get history: ${res.status}`);
  return res.json();
}

export function createSSEConnection(sessionId, taskId, handlers) {
  const url = `${BASE_URL}/session/${sessionId}/result/${taskId}`;
  const es = new EventSource(url);

  es.onmessage = (e) => {
    try {
      const parsed = JSON.parse(e.data);
      const { event, payload } = parsed;
      if (event === "node_complete") {
        handlers.onNodeComplete?.(payload);
      } else if (event === "done") {
        handlers.onDone?.(payload);
        es.close();
      } else if (event === "error") {
        handlers.onError?.(payload);
        es.close();
      }
    } catch {
      // ignore malformed events
    }
  };

  es.onerror = (e) => {
    handlers.onError?.({ error: "SSE connection error" });
    es.close();
  };

  return () => es.close();
}
