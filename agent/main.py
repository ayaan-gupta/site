"""
this is theFastAPI backend for the IRW chat widget.
POST /chat: user message + optional conversation history --> agent reply.
"""
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load .env from agent/ directory when running as uvicorn agent.main:app
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agent import run_agent

app = FastAPI(
    title="IRW Chat Agent",
    description="Agentic assistant to locate and process IRW datasets.",
)

# CORS so the Quarto site (e.g. different port or origin) can call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] | None = None


class ChatResponse(BaseModel):
    reply: str
    history: list[dict[str, Any]]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Run the agent on the user message, with optional conversation history."""
    history = []
    if req.history:
        for m in req.history:
            if m.role in ("user", "assistant") and m.content:
                history.append({"role": m.role, "content": m.content})
    history.append({"role": "user", "content": req.message})

    try:
        reply, updated = run_agent(
            history,
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Return only user/assistant messages for the client (no tool messages)
    out_history = [
        {"role": m["role"], "content": m.get("content", "")}
        for m in updated
        if m["role"] in ("user", "assistant")
    ]
    return ChatResponse(reply=reply, history=out_history)
