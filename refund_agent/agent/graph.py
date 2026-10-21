"""The conversation graph (plan section 5): LangGraph keeps the conversation, the tool results and the routing in
PostgreSQL, and grants nothing.

A run starts when something new arrives in a conversation (a customer message, or a backend event such as an
approval) and ends when the agent says something to the customer. Inside a run the graph alternates two nodes:
"agent" asks the model, and "tools" runs the calls the model made, each through call_tool with the call's own ID.
After every node the state is checkpointed in the graph schema, so after a crash resume() continues from the last
step, and a tool call that runs again gets the same request key: no second proposal and no second refund.

The checkpoint is memory, not authority. An event saying "approved" is only text for the model; execute_refund
still checks the database. Once a person has taken over, a new customer message is recorded and the model is not
asked at all.

What the customer and the agent say is also written to the messages table, which the screens and the evaluator read,
with an ID made from its place in the conversation, so writing it again after a restart changes nothing.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from operator import add
from typing import Annotated, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from sqlalchemy import Engine, text

from refund_agent.agent.model import Instructions, ModelAdapter, load_instructions
from refund_agent.agent.tools import ToolContext, call_tool, tool_definitions
from refund_agent.policy import Policy
from refund_agent.refunds import Configuration


class State(TypedDict):
    messages: Annotated[list[dict], add]
    usage: Annotated[list[dict], add]  # one entry per model request, for cost


class AgentLoopError(Exception):
    """The agent did not answer the customer within its step limit: a failure of the system (plan section 11)."""


class AgentBusy(Exception):
    """The agent is still answering in this conversation; one run at a time per conversation, in this process."""


class Agent:
    def __init__(
        self,
        engine: Engine,
        policy: Policy,
        model: ModelAdapter,
        checkpointer: BaseCheckpointSaver,
        clock: Callable[[], datetime],
        *,
        instructions: Instructions | None = None,
        configuration: Configuration = "A",
        max_steps: int = 12,
    ) -> None:
        """engine: the refund_app role. configuration "C" only in the isolated evaluation harness."""
        self.engine, self.policy, self.model, self.clock = engine, policy, model, clock
        self.instructions = instructions or load_instructions(policy=policy)
        self.configuration, self.max_steps = configuration, max_steps
        self.tools = tool_definitions()
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        graph = StateGraph(State)
        graph.add_node("agent", self._agent)
        graph.add_node("tools", self._tools)
        graph.add_edge(START, "agent")
        graph.add_conditional_edges("agent", self._route, {"tools": "tools", "end": END})
        graph.add_edge("tools", "agent")
        self.graph = graph.compile(checkpointer=checkpointer)

    # Nodes

    def _agent(self, state: State) -> dict:
        turn = self.model.respond(self.instructions.text, state["messages"], self.tools)
        return {"messages": [turn.as_message()], "usage": [{"model": turn.model, **asdict(turn.usage)}]}

    @staticmethod
    def _route(state: State) -> str:
        return "tools" if state["messages"][-1].get("tool_calls") else "end"

    def _tools(self, state: State, config: RunnableConfig) -> dict:
        ctx = self._context(config["configurable"]["thread_id"])
        results = []
        for call in state["messages"][-1]["tool_calls"]:
            result = call_tool(ctx, call["name"], call["arguments"], call["call_id"])
            results.append(
                {"role": "tool", "call_id": call["call_id"], "name": call["name"], "content": json.dumps(result)}
            )
        return {"messages": results}

    def _context(self, conversation_id: str) -> ToolContext:
        return ToolContext(
            self.engine,
            self.policy,
            self.clock,
            self._conversation(conversation_id)["customer_id"],
            conversation_id,
            self.configuration,
        )

    # Runs

    def receive(self, conversation_id: str, text_from_customer: str) -> list[dict]:
        """A customer message. Returns the messages this run added, ending with the agent's answer."""
        message = {"role": "customer", "text": text_from_customer}
        with self._turn(conversation_id, wait=False):
            if self._conversation(conversation_id)["control"] == "human_controlled":
                config = self._config(conversation_id)
                self.graph.update_state(config, {"messages": [message]}, as_node="agent")  # recorded, not answered
                self._mirror(conversation_id)
                return []
            return self._run(conversation_id, {"messages": [message]})

    def notify(self, conversation_id: str, event: str, notice_id: str | None = None) -> list[dict]:
        """A backend event, such as an approval. Only text for the model: it proves nothing. It waits for a run in
        progress instead of being lost, and wakes nobody once a person has taken over. A notice with an ID is applied
        once: delivered again, after a crash between this run and the mark of its delivery, it changes nothing. If
        the run it started stopped before its end (the model failed), delivering it again finishes that run, so a
        notice is never acknowledged with its work undone (review of 2026-10-19, R1)."""
        with self._turn(conversation_id, wait=True):
            if self._conversation(conversation_id)["control"] == "human_controlled":
                return []
            if notice_id and any(m.get("notice_id") == notice_id for m in self.messages(conversation_id)):
                if self.graph.get_state(self._config(conversation_id)).next:
                    return self._run(conversation_id, None)
                return []
            message = {"role": "event", "text": event} | ({"notice_id": notice_id} if notice_id else {})
            return self._run(conversation_id, {"messages": [message]})

    def resume(self, conversation_id: str) -> list[dict]:
        """Finish a run that stopped in the middle, for example after a crash."""
        with self._turn(conversation_id, wait=True):
            return self._run(conversation_id, None)

    def messages(self, conversation_id: str) -> list[dict]:
        return self.graph.get_state(self._config(conversation_id)).values.get("messages", [])

    def usage(self, conversation_id: str) -> list[dict]:
        return self.graph.get_state(self._config(conversation_id)).values.get("usage", [])

    def _config(self, conversation_id: str) -> RunnableConfig:
        return {"configurable": {"thread_id": conversation_id}, "recursion_limit": 2 * self.max_steps + 1}

    @contextmanager
    def _turn(self, conversation_id: str, *, wait: bool) -> Iterator[None]:
        with self._locks_guard:
            lock = self._locks.setdefault(conversation_id, threading.Lock())
        if not (lock.acquire(timeout=60) if wait else lock.acquire(blocking=False)):
            raise AgentBusy(f"the agent is still answering in {conversation_id}")
        try:
            yield
        finally:
            lock.release()

    def _run(self, conversation_id: str, start: dict | None) -> list[dict]:
        config = self._config(conversation_id)
        before = len(self.messages(conversation_id))
        try:
            if start is not None and self.graph.get_state(config).next:
                self._steps(conversation_id, None, config)  # first finish the run that a crash cut short
            self._steps(conversation_id, start, config)
        except GraphRecursionError as error:
            raise AgentLoopError(f"no answer to the customer within {self.max_steps} steps") from error
        finally:
            self._mirror(conversation_id)
        return self.messages(conversation_id)[before:]

    def _steps(self, conversation_id: str, start: dict | None, config: RunnableConfig) -> None:
        """Run the graph one step at a time and store what was said after each step, so a message is written before
        the tools of the same turn act, and messages and actions have one exact order (outside review of 2026-10-15).
        The state comes from the stream itself: the step's checkpoint may not be saved yet when the next step starts,
        so reading it back would store the message one step late."""
        for state in self.graph.stream(start, config, stream_mode="values"):
            self._mirror(conversation_id, state.get("messages", []))

    # The database

    def _conversation(self, conversation_id: str) -> dict:
        with self.engine.connect() as conn:
            found = (
                conn.execute(
                    text("SELECT customer_id, control FROM conversations WHERE id = :id"), {"id": conversation_id}
                )
                .mappings()
                .first()
            )
        if found is None:
            raise LookupError(f"no conversation {conversation_id}")
        return dict(found)

    def _mirror(self, conversation_id: str, messages: list[dict] | None = None) -> None:
        """Write what the customer and the agent said to the messages table, once per place in the conversation.
        `messages` is the conversation's state as the run has it; by default the last saved checkpoint."""
        said = self.messages(conversation_id) if messages is None else messages
        rows = [
            {
                "id": f"{conversation_id}/m{index:04d}",
                "conversation": conversation_id,
                "author": message["role"],
                "content": message["text"],
                "at": self.clock(),
            }
            for index, message in enumerate(said)
            if message["role"] in ("customer", "agent") and message.get("text")
        ]
        if rows:
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO messages (id, conversation_id, author, content_untrusted, created_at) "
                        "VALUES (:id, :conversation, :author, :content, :at) ON CONFLICT (id) DO NOTHING"
                    ),
                    rows,
                )
