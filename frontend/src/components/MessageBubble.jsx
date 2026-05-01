import ReasoningTrace from "./ReasoningTrace.jsx";

export default function MessageBubble({ message }) {
  const { role, content, traces, isStreaming } = message;

  return (
    <div className={`message ${role}`}>
      {role === "agent" && traces?.length > 0 && (
        <ReasoningTrace events={traces} />
      )}
      <div className="bubble">
        {content || (isStreaming ? "Thinking…" : "")}
      </div>
    </div>
  );
}
