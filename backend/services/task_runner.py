import asyncio
import json
import uuid
from typing import AsyncGenerator

import redis.asyncio as aioredis

from backend.agent.graph import agent_graph
from backend.agent.state import GraphState
from backend.memory import redis_store


class TaskRunner:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    async def submit_task(self, session_id: str, task: str) -> str:
        task_id = str(uuid.uuid4())

        await redis_store.set_task_status(
            self.redis,
            task_id,
            {"status": "pending", "session_id": session_id, "task": task},
        )

        asyncio.create_task(self._run(session_id, task_id, task))
        return task_id

    async def _run(self, session_id: str, task_id: str, task: str) -> None:
        await redis_store.set_task_status(
            self.redis, task_id, {"status": "running", "session_id": session_id}
        )

        # Check task result cache
        task_hash = redis_store.hash_task(task)
        cached = await redis_store.get_cached_result(self.redis, task_hash)
        if cached:
            final_response = cached.get("final_response", "")
            await redis_store.set_task_status(
                self.redis,
                task_id,
                {"status": "done", "final_response": final_response, "cached": True},
            )
            await redis_store.publish_progress(
                self.redis,
                task_id,
                "done",
                {"final_response": final_response, "cached": True},
            )
            return

        initial_state: GraphState = {
            "session_id": session_id,
            "task_id": task_id,
            "task": task,
            "task_plan": None,
            "generated_code": None,
            "execution_result": None,
            "reflector_decision": None,
            "error_trace": None,
            "retry_count": 0,
            "memory_context": None,
            "final_response": None,
            "syntax_error_count": 0,
        }

        try:
            final_state: GraphState = await agent_graph.ainvoke(initial_state)
            final_response = final_state.get("final_response") or "Task completed."

            await redis_store.set_task_status(
                self.redis,
                task_id,
                {"status": "done", "final_response": final_response},
            )
            await redis_store.publish_progress(
                self.redis,
                task_id,
                "done",
                {"final_response": final_response},
            )

            # Cache successful results
            decision = final_state.get("reflector_decision") or {}
            if decision.get("outcome") == "success":
                await redis_store.set_cached_result(
                    self.redis,
                    task_hash,
                    {"final_response": final_response},
                )

        except Exception as e:
            error_msg = f"Agent error: {e}"
            await redis_store.set_task_status(
                self.redis, task_id, {"status": "error", "error": error_msg}
            )
            await redis_store.publish_progress(
                self.redis,
                task_id,
                "error",
                {"error": error_msg},
            )

    async def get_task_status(self, task_id: str) -> dict | None:
        return await redis_store.get_task_status(self.redis, task_id)

    async def stream_task_events(self, task_id: str) -> AsyncGenerator[str, None]:
        # Check if already done before subscribing
        status = await self.get_task_status(task_id)
        if status and status.get("status") in ("done", "error"):
            event_type = "done" if status.get("status") == "done" else "error"
            payload = (
                {"final_response": status.get("final_response")}
                if event_type == "done"
                else {"error": status.get("error")}
            )
            data = json.dumps({"event": event_type, "task_id": task_id, "payload": payload})
            yield f"data: {data}\n\n"
            return

        channel = f"{redis_store.TASK_UPDATES_PREFIX}{task_id}"
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)

        try:
            heartbeat_interval = 15
            elapsed = 0
            while True:
                message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0), timeout=2.0)
                if message and message["type"] == "message":
                    raw = message["data"]
                    parsed = json.loads(raw)
                    event = parsed.get("event", "update")
                    payload = parsed.get("payload", {})
                    data = json.dumps({"event": event, "task_id": task_id, "payload": payload})
                    yield f"data: {data}\n\n"
                    if event in ("done", "error"):
                        break
                else:
                    elapsed += 1
                    if elapsed >= heartbeat_interval:
                        yield f"data: {json.dumps({'event': 'heartbeat', 'task_id': task_id})}\n\n"
                        elapsed = 0

                # Safety: re-check Redis status in case pub/sub message was missed
                current = await self.get_task_status(task_id)
                if current and current.get("status") in ("done", "error"):
                    break

        except asyncio.TimeoutError:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
