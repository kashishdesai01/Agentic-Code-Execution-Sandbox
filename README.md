# Agentic Code Execution Sandbox

A multi-turn agentic system where a user describes a task in natural language and an autonomous agent independently writes Python code, executes it inside a locked-down Docker sandbox, observes the output, reflects on whether it succeeded, and retries until the task is complete — or explains why it failed.

---

## Architecture

```
User Input
    │
    ▼
┌─────────┐     structured plan     ┌───────────────┐
│ Planner │ ─────────────────────► │ Code Generator│
└─────────┘                        └───────┬───────┘
     ▲                                     │ Python code
     │                                     ▼
     │                             ┌──────────────┐
     │                             │   Executor   │  ← Docker container
     │                             │  (sandboxed) │    --network none
     │                             └──────┬───────┘    --read-only
     │                                    │ stdout/stderr/exit_code
     │                                    ▼
     │                            ┌────────────────┐
     │    retry (up to 3×) ◄──── │   Reflector    │ ──► success → User
     └────────────────────────── └────────────────┘
```

The system is built on **LangGraph** with a conditional DAG: four nodes wired so the Reflector can route back to the Code Generator on retryable failures, up to a configurable retry limit.

### Node Responsibilities

| Node | What It Does |
|------|-------------|
| **Planner** | Converts the user's natural language task into a structured `TaskPlan` (objective, steps, success criteria). Retrieves prior session context from Redis. |
| **Code Generator** | Calls Claude to write Python, strips markdown fences, validates syntax with `ast.parse()`, performs one internal retry on syntax errors. |
| **Executor** | Writes code to a temp file, runs `docker run` with full isolation flags, captures stdout/stderr/exit_code, enforces a 10-second timeout via `asyncio.wait_for`. |
| **Reflector** | Evaluates whether execution succeeded against the task plan's success criteria. Routes to retry, success, or hard failure. Persists outcomes to Redis. |

---

## Sandbox Isolation

Code runs inside a pre-built Docker image with layered constraints:

```bash
docker run \
  --rm \
  --network none \          # no internet access
  --read-only \             # no filesystem writes
  --memory 128m \           # hard memory cap
  --cpus 0.5 \              # CPU throttle
  --tmpfs /tmp:size=64m,noexec \   # writable scratch, no exec
  -v /tmp/task_<id>.py:/sandbox/task.py:ro \
  --user sandbox \          # non-root user
  sandbox-image \
  python /sandbox/task.py
```

**Import whitelist** enforced at interpreter startup via `sitecustomize.py` — a custom `builtins.__import__` hook that raises `ImportError` for anything outside:

```
math  json  re  collections  itertools  datetime  string  random
```

Any attempt to import `requests`, `os`, `subprocess`, `socket`, or any other module raises an error before execution proceeds.

---

## Agent Memory (Redis)

Two data structures, both with TTLs:

**Session store** — `session:<session_id>` (TTL: 7 days)
```json
{
  "task_history": [{"task_id": "...", "task": "...", "outcome": "success", "timestamp": "..."}],
  "last_successful_code": "...",
  "last_error": "...",
  "created_at": "...",
  "updated_at": "..."
}
```

**Result cache** — `tool_result:<sha256_of_task>` (TTL: 1 day)  
Identical tasks skip the graph entirely and return the cached result instantly.

The Planner reads session memory at the start of every turn, injecting prior successful code and error context into its prompt. The Reflector writes back on success or failure.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | LangGraph (StateGraph) |
| LLM | Claude via `langchain-anthropic` |
| Structured output | Claude tool-use (`with_structured_output`) |
| Sandbox | Docker (`python:3.11-slim`, non-root, import whitelist) |
| Memory | Redis (session store + result cache + pub/sub for SSE) |
| API | FastAPI + SSE via `sse-starlette` |
| Frontend | React + Vite + Prism.js |

---

## Project Structure

```
├── backend/
│   ├── main.py                  # FastAPI app + lifespan
│   ├── config.py                # Pydantic Settings
│   ├── dependencies.py          # FastAPI Depends() providers
│   ├── agent/
│   │   ├── state.py             # All Pydantic models + GraphState TypedDict
│   │   ├── graph.py             # LangGraph wiring
│   │   ├── nodes/               # planner, code_generator, executor, reflector
│   │   └── prompts/             # System + human prompt builders
│   ├── memory/
│   │   └── redis_store.py       # Session memory, result cache, pub/sub
│   ├── services/
│   │   └── task_runner.py       # Async task orchestration + SSE streaming
│   └── api/
│       ├── sessions.py          # POST /session, DELETE /session/{id}
│       └── tasks.py             # POST /run, GET /result/{id} (SSE), GET /history
│
├── sandbox/
│   ├── Dockerfile               # Sandbox image definition
│   └── sitecustomize.py         # Import whitelist hook
│
├── frontend/
│   └── src/
│       ├── App.jsx              # Main app shell
│       ├── api/client.js        # fetch + EventSource wrappers
│       ├── components/
│       │   ├── ChatWindow.jsx
│       │   ├── MessageBubble.jsx
│       │   ├── ReasoningTrace.jsx  # Collapsible per-retry trace panels
│       │   └── CodeBlock.jsx       # Prism.js syntax highlighting
│       └── hooks/
│           ├── useSession.js    # localStorage-backed session persistence
│           └── useSSE.js        # EventSource wrapper hook
│
└── tests/
    ├── test_state.py            # Pydantic model round-trip tests
    ├── test_nodes.py            # Unit tests: routing logic, strip_fences, fast-path executor
    ├── test_executor.py         # Docker integration tests (skipped if Docker unavailable)
    ├── test_graph.py            # Full graph run with mocked LLM + executor
    └── test_api.py              # FastAPI endpoint tests (httpx AsyncClient)
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/session/` | Create a new session → `{session_id}` |
| `DELETE` | `/api/v1/session/{id}` | Delete session and clear Redis memory |
| `POST` | `/api/v1/session/{id}/run` | Submit a task → `{task_id}` (returns immediately) |
| `GET` | `/api/v1/session/{id}/result/{task_id}` | Stream task progress as SSE |
| `GET` | `/api/v1/session/{id}/history` | Full task history for this session |
| `GET` | `/health` | Health check |

**SSE event stream format:**
```
data: {"event": "node_complete", "task_id": "...", "payload": {"node": "planner", "task_plan": {...}}}

data: {"event": "node_complete", "task_id": "...", "payload": {"node": "code_generator", "code": "..."}}

data: {"event": "node_complete", "task_id": "...", "payload": {"node": "executor", "stdout": "...", "exit_code": 0}}

data: {"event": "node_complete", "task_id": "...", "payload": {"node": "reflector", "outcome": "success"}}

data: {"event": "done", "task_id": "...", "payload": {"final_response": "..."}}
```

---

## Setup

### Prerequisites

- Python 3.11+
- Docker (running)
- Redis 7+
- Node.js 18+ (for frontend)
- An Anthropic API key

### 1. Clone and install

```bash
git clone <repo-url>
cd Agentic-Code-Execution-Sandbox

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-...
REDIS_URL=redis://localhost:6379
SANDBOX_IMAGE=sandbox-image
DOCKER_TIMEOUT_SECONDS=10
DOCKER_MEMORY=128m
DOCKER_CPUS=0.5
MAX_RETRIES=3
CLAUDE_MODEL=claude-sonnet-4-6
API_HOST=0.0.0.0
API_PORT=8000
```

### 3. Build the Docker sandbox image

```bash
docker build -t sandbox-image ./sandbox/
```

Verify isolation is working:
```bash
# Should print 3.14159...
docker run --rm --network none --read-only --memory 128m --cpus 0.5 \
  --tmpfs /tmp sandbox-image python -c "import math; print(math.pi)"

# Should fail with ImportError
docker run --rm --network none --read-only --memory 128m --cpus 0.5 \
  --tmpfs /tmp sandbox-image python -c "import requests"
```

### 4. Start Redis

```bash
docker run -d -p 6379:6379 redis:7
```

### 5. Start the backend

```bash
uvicorn backend.main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

### 6. Start the frontend

```bash
cd frontend

# Create frontend/.env
echo "VITE_API_BASE_URL=http://localhost:8000/api/v1" > .env

npm install
npm run dev
# → http://localhost:5173
```

---

## Running Tests

```bash
# Unit tests — no external dependencies needed
pytest tests/test_state.py tests/test_nodes.py -v

# API tests — no external dependencies needed
pytest tests/test_api.py -v

# Graph integration tests — no external dependencies needed (mocked LLM + executor)
pytest tests/test_graph.py -v

# Docker integration tests — requires Docker + sandbox-image built
pytest tests/test_executor.py -v

# All tests
pytest -v
```

---

## Frontend

The React UI streams agent reasoning in real-time:

- Each task submission opens an **SSE connection** that delivers events as each node completes
- **Per-retry trace panels** collapse/expand — showing the plan, generated code (syntax-highlighted), execution output, and the reflector's verdict for each attempt
- Session ID is persisted in `localStorage` and mapped to Redis-backed session memory on the backend
- The agent's final response appears in the chat bubble once streaming completes

---

## Design Decisions

**Why Docker and not just subprocess?**  
Subprocess isolation is insufficient — a script can still read host environment variables, make network calls, and consume unbounded memory. Docker provides real namespace isolation, network control, and resource caps with one flag each. The container is destroyed after every run (`--rm`).

**Why Redis pub/sub for SSE instead of LangGraph streaming?**  
LangGraph's `.astream()` works at the graph level. Wiring that cleanly to HTTP SSE — especially across retry cycles — adds complexity. Redis pub/sub decouples graph execution from the HTTP layer: each node publishes a progress event, the SSE endpoint just subscribes. This also makes horizontal scaling possible later.

**Why Redis and not a vector DB for memory?**  
For session memory, recency and exact session identity matter more than semantic similarity. Redis TTL-keyed storage is simpler, faster, and operationally lighter. Cross-session semantic retrieval (find tasks similar to the current one across all users) would be a natural addition with pgvector.

**Why `langchain-anthropic` with `with_structured_output` instead of the raw Anthropic SDK?**  
It uses Claude's native tool-use to produce JSON conforming to a Pydantic schema, eliminating manual JSON parsing and validation. The planner and reflector always return typed `TaskPlan` and `ReflectorDecision` objects — no regex, no try/except JSON parsing.

**Why is the syntax retry inside the node and not a graph edge?**  
The code generator gets at most one internal syntax-fix pass before returning. Keeping this inside the node preserves the graph's clean topology — only the Reflector's retry uses a graph edge. The graph edge retry is bounded by `MAX_RETRIES`; the syntax retry is bounded by the node itself.
