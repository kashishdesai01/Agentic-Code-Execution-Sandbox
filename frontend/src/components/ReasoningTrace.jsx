import CodeBlock from "./CodeBlock.jsx";

function OutcomeBadge({ outcome }) {
  return (
    <span className={`outcome-badge outcome-${outcome}`}>
      {outcome.replace("_", " ")}
    </span>
  );
}

export default function ReasoningTrace({ events }) {
  // Group events by retry cycle: each cycle contains planner/code_generator/executor/reflector
  const cycles = [];
  let current = {};

  for (const event of events) {
    const { node, retry_count = 0, ...rest } = event;
    const cycle = retry_count;

    if (!cycles[cycle]) cycles[cycle] = {};
    cycles[cycle][node] = rest;
  }

  if (cycles.length === 0) return null;

  return (
    <div className="trace-container">
      {cycles.map((cycle, i) => (
        <details key={i} className="trace-panel" open={i === cycles.length - 1}>
          <summary>
            <span>&#9654;</span>
            {i === 0 ? "Attempt 1" : `Retry ${i}`}
            {cycle.reflector && (
              <OutcomeBadge outcome={cycle.reflector.outcome} />
            )}
          </summary>
          <div className="trace-body">
            {cycle.planner && (
              <div className="trace-section">
                <h4>Plan</h4>
                <p>{cycle.planner.task_plan?.objective}</p>
                {cycle.planner.task_plan?.steps && (
                  <ul style={{ paddingLeft: 16, marginTop: 4, fontSize: 13, color: "#aaa" }}>
                    {cycle.planner.task_plan.steps.map((s, j) => <li key={j}>{s}</li>)}
                  </ul>
                )}
              </div>
            )}
            {cycle.code_generator?.code && (
              <div className="trace-section">
                <h4>Generated Code</h4>
                <CodeBlock code={cycle.code_generator.code} />
              </div>
            )}
            {cycle.executor && (
              <div className="trace-section">
                <h4>Execution</h4>
                <div className="exec-result">
                  {cycle.executor.stdout && (
                    <div className="exec-stdout">stdout: {cycle.executor.stdout}</div>
                  )}
                  {cycle.executor.stderr && (
                    <div className="exec-stderr">stderr: {cycle.executor.stderr}</div>
                  )}
                  <div className="exec-meta">
                    exit_code: {cycle.executor.exit_code}
                    {cycle.executor.timed_out && " · timed out"}
                  </div>
                </div>
              </div>
            )}
            {cycle.reflector && (
              <div className="trace-section">
                <h4>Reflection</h4>
                <p style={{ fontSize: 13, color: "#aaa" }}>{cycle.reflector.reasoning}</p>
                {cycle.reflector.suggested_fix && (
                  <p style={{ fontSize: 12, color: "#888", marginTop: 4 }}>
                    Fix: {cycle.reflector.suggested_fix}
                  </p>
                )}
              </div>
            )}
          </div>
        </details>
      ))}
    </div>
  );
}
