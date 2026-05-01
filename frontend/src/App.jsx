import { useState, useRef } from "react";
import { submitTask, createSSEConnection } from "./api/client.js";
import { useSession } from "./hooks/useSession.js";
import ChatWindow from "./components/ChatWindow.jsx";

let _msgId = 0;
const nextId = () => String(++_msgId);

export default function App() {
  const { sessionId, loading: sessionLoading } = useSession();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const sseCleanupRef = useRef(null);

  function patchAgent(id, fn) {
    setMessages((prev) => prev.map((m) => (m.id === id ? fn(m) : m)));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const task = input.trim();
    if (!task || !sessionId || busy) return;

    setInput("");
    setBusy(true);

    const userMsg = { id: nextId(), role: "user", content: task };
    const agentId = nextId();
    const agentMsg = { id: agentId, role: "agent", content: "", traces: [], isStreaming: true };

    setMessages((prev) => [...prev, userMsg, agentMsg]);

    let taskId;
    try {
      ({ task_id: taskId } = await submitTask(sessionId, task));
    } catch (err) {
      patchAgent(agentId, (m) => ({
        ...m,
        content: `Failed to submit task: ${err.message}`,
        isStreaming: false,
      }));
      setBusy(false);
      return;
    }

    if (sseCleanupRef.current) sseCleanupRef.current();

    sseCleanupRef.current = createSSEConnection(sessionId, taskId, {
      onNodeComplete: (payload) => {
        patchAgent(agentId, (m) => ({ ...m, traces: [...m.traces, payload] }));
      },
      onDone: (payload) => {
        patchAgent(agentId, (m) => ({
          ...m,
          content: payload.final_response || "Done.",
          isStreaming: false,
        }));
        setBusy(false);
      },
      onError: (payload) => {
        patchAgent(agentId, (m) => ({
          ...m,
          content: `Error: ${payload.error || "Unknown error"}`,
          isStreaming: false,
        }));
        setBusy(false);
      },
    });
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }

  return (
    <>
      <ChatWindow messages={messages} />
      <div style={{ borderTop: "1px solid #222", background: "#0f0f0f" }}>
        <form className="input-bar" onSubmit={handleSubmit}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={sessionLoading ? "Connecting…" : "Describe a task for the agent…"}
            disabled={busy || sessionLoading}
            rows={1}
          />
          <button type="submit" disabled={busy || sessionLoading || !input.trim()}>
            {busy ? "Running…" : "Run"}
          </button>
        </form>
        {sessionId && (
          <p className="status-line" style={{ textAlign: "center", paddingBottom: 8 }}>
            Session: {sessionId.slice(0, 8)}…
          </p>
        )}
      </div>
    </>
  );
}
