"""The HTTP layer: the doors of the customer screen and the staff console (plan sections 5, 7 and 8).

Who acts comes from the session and from the door: the customer's doors act as Actor("customer", user), the
console's as Actor("staff", user), and a signed-in user of the other role is refused at the door. Request bodies carry
only the sign-in fields or a decision; any other field, such as an amount, an actor or a configuration, makes the
request invalid. Every change needs the session's CSRF token in the X-CSRF-Token header.

There is no door that proposes or executes a refund: those are tools of the agent, which runs inside the backend in
the customer's session. The chat door only hands the customer's text to the agent, and a staff decision wakes the
agent with a notice, after the answer is sent. The agent is built once when the server starts, and create_app refuses
one in any configuration but A, so configuration C cannot be chosen or reached over HTTP.

A refusal by a domain service becomes an HTTP error that names the check. Anything that belongs to another customer
is "not found", so its existence is not revealed.
"""

# No `from __future__ import annotations` here: FastAPI reads the parameter types of the routes, and the session
# dependencies are defined inside create_app, where string annotations could not be resolved.
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine, text

from refund_agent import reads
from refund_agent.agent.graph import Agent, AgentBusy, AgentLoopError
from refund_agent.agent.model import ModelError
from refund_agent.api import auth
from refund_agent.policy import Policy
from refund_agent.refunds import Actor, Refused, cancel, confirm, decide, hand_off, open_conversation, take_handoff

Clock = Callable[[], datetime]

# A refused check becomes this status; any other check is a conflict with the current state (409).
STATUS_OF_CHECK = {"actor_owns": 404, "staff_role": 403, "valid_values": 422}


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SignInBody(_Body):
    email: str = Field(max_length=320)
    password: str = Field(max_length=200)


class ConfirmationBody(_Body):
    decision: Literal["confirmed", "declined"]


class MessageBody(_Body):
    text: str = Field(min_length=1, max_length=2000)


class DecisionBody(_Body):
    decision: Literal["approved", "rejected"]


def _real_time() -> datetime:
    return datetime.now(UTC)


def _not_found() -> HTTPException:
    return HTTPException(404, "not_found")


def create_app(
    engine: Engine,
    policy: Policy,
    clock: Clock,
    *,
    wall_clock: Clock = _real_time,
    secure_cookies: bool = True,
    agent: Agent | None = None,
) -> FastAPI:
    """engine: the refund_app role. clock: the business time given to the services. wall_clock: real time, for
    sessions. secure_cookies: False only for a local demo over plain HTTP. agent: the agent behind the chat door,
    always in configuration A; without one the chat door answers 503."""
    if agent is not None and agent.configuration != "A":
        raise ValueError("the lab configuration is never served over HTTP (plan section 10.5)")
    log = logging.getLogger("refund_agent.api")
    app = FastAPI(
        title="Reliable Refund Agent",
        version="0.0.1",
        summary="Customer screen and staff console. Refunds are proposed and executed only by the agent.",
    )

    @app.exception_handler(Refused)
    async def refused(request: Request, refusal: Refused) -> JSONResponse:
        status = STATUS_OF_CHECK.get(refusal.check, 409)
        if status == 404:
            return JSONResponse({"detail": "not_found"}, status_code=404)
        return JSONResponse({"detail": refusal.check, "explanation": refusal.detail}, status_code=status)

    def signed_in(request: Request) -> auth.SignedIn:
        token = request.cookies.get(auth.SESSION_COOKIE)
        user = auth.session_user(engine, token, wall_clock()) if token else None
        if user is None:
            raise HTTPException(401, "sign in first")
        return user

    def changing(request: Request, x_csrf_token: Annotated[str | None, Header()] = None) -> auth.SignedIn:
        user = signed_in(request)
        if not auth.csrf_matches(user, x_csrf_token):
            raise HTTPException(403, f"missing or wrong {auth.CSRF_HEADER} header")
        return user

    Reading = Annotated[auth.SignedIn, Depends(signed_in)]
    Changing = Annotated[auth.SignedIn, Depends(changing)]

    def customer(user: auth.SignedIn) -> Actor:
        if user.role != "customer":
            raise HTTPException(403, "this door is for customers")
        return Actor("customer", user.user_id)

    def staff(user: auth.SignedIn) -> Actor:
        if user.role != "staff":
            raise HTTPException(403, "this door is for staff")
        return Actor("staff", user.user_id)

    def me(user: auth.SignedIn) -> dict:
        return {
            "user_id": user.user_id,
            "role": user.role,
            "display_name": user.display_name,
            "csrf_token": user.csrf_token,
        }

    # Health and session

    @app.get("/api/health")
    def health() -> dict:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}

    @app.post("/api/session")
    def sign_in(body: SignInBody, response: Response) -> dict:
        signed = auth.sign_in(engine, body.email, body.password, wall_clock())
        if signed is None:
            raise HTTPException(401, "wrong email or password")
        token, user = signed
        response.set_cookie(
            auth.SESSION_COOKIE,
            token,
            max_age=int(auth.SESSION_LIFETIME.total_seconds()),
            httponly=True,
            secure=secure_cookies,
            samesite="strict",
        )
        return me(user)

    @app.get("/api/session")
    def current_session(user: Reading) -> dict:
        return me(user)

    @app.delete("/api/session")
    def sign_out(request: Request, response: Response, user: Changing) -> dict:
        auth.sign_out(engine, request.cookies[auth.SESSION_COOKIE], wall_clock())
        response.delete_cookie(auth.SESSION_COOKIE, httponly=True, secure=secure_cookies, samesite="strict")
        return {"signed_out": True}

    # The customer's doors

    @app.get("/api/orders")
    def my_orders(user: Reading) -> list[dict]:
        actor = customer(user)
        with engine.connect() as conn:
            return reads.orders(conn, actor.user_id, policy.currency)

    @app.post("/api/conversations", status_code=201)
    def start_conversation(user: Changing) -> dict:
        return {"conversation_id": open_conversation(engine, customer(user), clock())}

    @app.get("/api/conversations/{conversation_id}")
    def my_conversation(conversation_id: str, user: Reading) -> dict:
        actor = customer(user)
        with engine.connect() as conn:
            found = reads.conversation(conn, conversation_id, clock())
        if found is None or found["customer_id"] != actor.user_id:
            raise _not_found()
        return found

    @app.post("/api/proposals/{proposal_id}/confirmation")
    def confirm_proposal(proposal_id: str, body: ConfirmationBody, user: Changing) -> dict:
        status = confirm(engine, customer(user), proposal_id, body.decision, clock(), policy)
        return {"proposal_id": proposal_id, "status": status}

    @app.post("/api/proposals/{proposal_id}/cancellation")
    def cancel_proposal(proposal_id: str, user: Changing) -> dict:
        return {"proposal_id": proposal_id, "status": cancel(engine, customer(user), proposal_id, clock(), policy)}

    @app.post("/api/conversations/{conversation_id}/handoff", status_code=201)
    def ask_for_a_person(conversation_id: str, user: Changing) -> dict:
        reason = "the customer asked for a person"
        return {"handoff_id": hand_off(engine, customer(user), conversation_id, reason, clock())}

    @app.post("/api/conversations/{conversation_id}/messages")
    def talk_to_the_agent(conversation_id: str, body: MessageBody, user: Changing) -> dict:
        actor = customer(user)
        with engine.connect() as conn:
            owner = conn.execute(
                text("SELECT customer_id FROM conversations WHERE id = :id"), {"id": conversation_id}
            ).scalar()
        if owner != actor.user_id:
            raise _not_found()
        if agent is None:
            raise HTTPException(503, "the agent is not running")
        try:
            added = agent.receive(conversation_id, body.text)
        except AgentBusy as busy:
            raise HTTPException(409, "the agent is still answering the previous message") from busy
        except (ModelError, AgentLoopError) as failure:
            log.warning("the agent could not answer in %s: %s", conversation_id, failure)
            raise HTTPException(503, "the agent could not answer; please try again") from failure
        return {"answers": [m["text"] for m in added if m["role"] == "agent" and m.get("text")]}

    # The staff console's doors

    @app.get("/api/staff/queue")
    def queue(user: Reading) -> dict:
        staff(user)
        with engine.connect() as conn:
            return reads.staff_queue(conn, clock())

    @app.get("/api/staff/proposals/{proposal_id}")
    def staff_proposal(proposal_id: str, user: Reading) -> dict:
        staff(user)
        with engine.connect() as conn:
            proposal = conn.execute(text("SELECT * FROM proposals WHERE id = :id"), {"id": proposal_id}).mappings()
            found = proposal.first()
            if found is None:
                raise _not_found()
            return reads.staff_proposal(conn, found, clock())

    @app.get("/api/staff/conversations/{conversation_id}")
    def staff_conversation(conversation_id: str, user: Reading) -> dict:
        staff(user)
        with engine.connect() as conn:
            found = reads.conversation(conn, conversation_id, clock())
        if found is None:
            raise _not_found()
        return found

    @app.post("/api/staff/proposals/{proposal_id}/decision")
    def decide_proposal(proposal_id: str, body: DecisionBody, user: Changing, background: BackgroundTasks) -> dict:
        status = decide(engine, staff(user), proposal_id, body.decision, clock(), policy)
        if agent is not None and status in ("approved", "rejected"):
            with engine.connect() as conn:
                conversation = conn.execute(
                    text("SELECT conversation_id FROM proposals WHERE id = :id"), {"id": proposal_id}
                ).scalar_one()
            background.add_task(wake, conversation, f"Request {proposal_id} was {status} by a staff member.")
        return {"proposal_id": proposal_id, "status": status}

    def wake(conversation_id: str, event: str) -> None:
        """After the staff answer is sent. The decision is already stored, whatever happens here."""
        try:
            agent.notify(conversation_id, event)
        except Exception:
            log.exception("the agent could not be woken in %s; the customer's next message continues", conversation_id)

    @app.post("/api/staff/handoffs/{handoff_id}/take")
    def take(handoff_id: str, user: Changing) -> dict:
        take_handoff(engine, staff(user), handoff_id, clock())
        return {"handoff_id": handoff_id, "status": "taken"}

    @app.post("/api/staff/conversations/{conversation_id}/takeover", status_code=201)
    def take_over(conversation_id: str, user: Changing) -> dict:
        reason = "a staff member took over"
        return {"handoff_id": hand_off(engine, staff(user), conversation_id, reason, clock())}

    return app
