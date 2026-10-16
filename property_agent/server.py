"""Web server for the website chat widget.

Run locally:
    uvicorn property_agent.server:app --reload
Then open http://localhost:8000 to try the demo page.

Environment variables:
    ANTHROPIC_API_KEY   required, your Claude API key (kept on the server, never sent to browsers)
    ALLOWED_ORIGINS     comma-separated websites allowed to embed the chat, e.g. https://www.myagency.sg
                        (default "*" allows any site - set this before going live)
    AGENT_NAME          name shown in the chat header (default "Property Advisor")
    LEADS_FILE          where captured leads are written (default leads.jsonl)
    ADMIN_TOKEN         if set, GET /admin/leads?token=... returns captured leads
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from . import agent as agent_module
from .agent import PropertyAdvisorAgent

STATIC_DIR = Path(__file__).parent / "static"
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
AGENT_NAME = os.environ.get("AGENT_NAME", "Property Advisor")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

SESSION_TTL_SECONDS = 60 * 60          # forget idle chats after 1 hour
MAX_SESSIONS = 2000
MAX_MESSAGES_PER_SESSION = 40
MAX_MESSAGE_CHARS = 2000
RATE_LIMIT_PER_IP = 20                 # messages per IP...
RATE_WINDOW_SECONDS = 10 * 60          # ...per 10 minutes

GREETING = (
    "Hi! I can help you work out which property suits your next move: HDB resale, new-launch EC, "
    "condo or landed. To start, are you a Singapore Citizen, PR or foreigner, and are you buying "
    "alone or with someone?"
)

app = FastAPI(title="Property Advisor Chat")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


class Session:
    def __init__(self):
        self.agent = PropertyAdvisorAgent(client=client())
        # Seed the greeting so Claude knows what the client has already been asked.
        self.agent.messages.append({"role": "user", "content": "Hi, I'm looking at my property options."})
        self.agent.messages.append({"role": "assistant", "content": GREETING})
        self.last_seen = time.time()
        self.user_messages = 0
        self.lock = asyncio.Lock()


_sessions: dict[str, Session] = {}
_hits: dict[str, deque] = defaultdict(deque)


def _prune_sessions():
    now = time.time()
    for sid in [s for s, v in _sessions.items() if now - v.last_seen > SESSION_TTL_SECONDS]:
        _sessions.pop(sid, None)
    while len(_sessions) > MAX_SESSIONS:
        oldest = min(_sessions, key=lambda s: _sessions[s].last_seen)
        _sessions.pop(oldest, None)


def _rate_limited(ip: str) -> bool:
    now, q = time.time(), _hits[ip]
    while q and now - q[0] > RATE_WINDOW_SECONDS:
        q.popleft()
    if len(q) >= RATE_LIMIT_PER_IP:
        return True
    q.append(now)
    return False


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


class ChatRequest(BaseModel):
    session_id: str | None = Field(default=None, max_length=64)
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


@app.get("/api/config")
def config():
    return {"agent_name": AGENT_NAME, "greeting": GREETING}


@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    if _rate_limited(_client_ip(request)):
        raise HTTPException(429, "You're sending messages too quickly. Please wait a few minutes.")
    _prune_sessions()
    sid = req.session_id if req.session_id in _sessions else secrets.token_urlsafe(16)
    session = _sessions.setdefault(sid, Session())
    if session.user_messages >= MAX_MESSAGES_PER_SESSION:
        return {"session_id": sid, "reply": "We've covered a lot! To go further, please leave your name and "
                                            "number, or contact the agent directly."}
    async with session.lock:
        session.last_seen = time.time()
        session.user_messages += 1
        try:
            reply = await asyncio.to_thread(session.agent.send, req.message.strip())
        except anthropic.RateLimitError:
            raise HTTPException(503, "The advisor is busy right now. Please try again in a minute.")
        except anthropic.APIStatusError as exc:
            # Drop the unanswered user turn so the conversation stays valid for the next try.
            _rollback(session.agent)
            raise HTTPException(502, f"The advisor couldn't answer (error {exc.status_code}). Please try again.")
        except anthropic.APIConnectionError:
            _rollback(session.agent)
            raise HTTPException(502, "Couldn't reach the advisor. Please try again.")
    return {"session_id": sid, "reply": reply}


def _rollback(agent: PropertyAdvisorAgent):
    """Remove messages back to (and including) the last plain-text user turn."""
    while agent.messages:
        msg = agent.messages.pop()
        if msg["role"] == "user" and isinstance(msg["content"], str):
            break


@app.get("/admin/leads")
def leads(token: str = ""):
    if not ADMIN_TOKEN or not secrets.compare_digest(token, ADMIN_TOKEN):
        raise HTTPException(404)
    path = Path(agent_module.LEADS_FILE)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []
    return JSONResponse(rows)


@app.get("/widget.js")
def widget():
    return FileResponse(STATIC_DIR / "widget.js", media_type="application/javascript",
                        headers={"Cache-Control": "public, max-age=300"})


@app.get("/", response_class=HTMLResponse)
def demo():
    return (STATIC_DIR / "demo.html").read_text(encoding="utf-8")


@app.get("/healthz")
def health():
    return {"ok": True}
