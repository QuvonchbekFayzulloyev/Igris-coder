"""
igris.server
-------------
The local HTTP/WebSocket bridge between the Tauri+React desktop UI and
the Python backend. Nothing in igris/core needs the UI to exist -- this
module is purely an adapter: REST for state (projects/skills/tools/
providers), one WebSocket for running a task with live stage-by-stage
progress (feeds the UI's Runtime/Loop/Logs panel).

Run standalone for development:
    uvicorn igris.server:app --reload --port 8765

In the shipped desktop app, Tauri's Rust shell spawns this as a sidecar
process on a local port and the React frontend talks to it over
localhost -- see src-tauri/src/main.rs.
"""
from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any

import httpx
import time

from . import workspace
from .config import Config
from .core.context_engine import ContextEngine
from .core.cost import estimate_cost_usd
from .core.gateway import build_llm
from .core.intent_resolver import IntentResolver
from .core.mcp_manager import MCPManager
from .core.reprompt_loop import RepromptLoop
from .core.skill_loader import SkillLoader
from .memory import Memory

app = FastAPI(title="igris-server")


@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(status_code=400, content={"error": str(exc)})


# The desktop UI loads from a tauri:// / localhost origin depending on
# platform; CORS is opened for local dev (Vite on 5173) and tightened by
# Tauri's own origin allowlist in production, not by this server.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "tauri://localhost", "http://tauri.localhost"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    project: str | None = None


class NewProjectRequest(BaseModel):
    name: str


class SelectProviderRequest(BaseModel):
    provider: str


class ProviderSettings(BaseModel):
    host: str | None = None
    model: str | None = None
    temperature: float | None = None
    api_key: str | None = None


class SettingsUpdate(BaseModel):
    provider: str | None = None  # shorthand for gateway.provider
    ollama: ProviderSettings | None = None
    lmstudio: ProviderSettings | None = None
    openrouter: ProviderSettings | None = None


def _config_for(project_name: str | None) -> Config:
    try:
        root = workspace.resolve_project_root(project_name)
    except workspace.NoProjectSelected as e:
        raise ValueError(str(e))
    config = Config.load(project_root=root)
    config.ensure_project_scaffold()
    return config


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/projects")
async def list_projects():
    return {"projects": workspace.list_projects(), "active": workspace.get_active_project()}


@app.post("/api/projects")
async def create_project(req: NewProjectRequest):
    path = workspace.create_project(req.name)
    config = Config.load(project_root=path)
    config.ensure_project_scaffold()
    workspace.set_active_project(req.name)
    return {"name": req.name, "path": str(path)}


@app.post("/api/projects/{name}/activate")
async def activate_project(name: str):
    if not workspace.project_exists(name):
        return {"error": f"project '{name}' not found"}
    workspace.set_active_project(name)
    return {"active": name}


@app.get("/api/skills")
async def list_skills(project: str | None = None):
    config = _config_for(project)
    loader = SkillLoader(config)
    return {
        "skills": [
            {
                "name": s.name,
                "description": s.description,
                "pipeline_stage": s.pipeline_stage,
                "triggers": s.triggers,
            }
            for s in loader.all()
        ]
    }


@app.get("/api/providers")
async def list_providers():
    return {
        "providers": ["ollama", "lmstudio", "openrouter"],
    }


class ModelsRequest(BaseModel):
    provider: str
    host: str
    api_key: str | None = None


@app.post("/api/providers/models")
async def fetch_models(req: ModelsRequest, project: str | None = None):
    """Fetch available models from a provider."""
    config = _config_for(project)
    provider = req.provider.lower()
    host = req.host

    if provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{host.rstrip('/')}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                return {"models": models}
        except Exception as e:
            return {"models": [], "error": str(e)}

    if provider == "lmstudio":
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{host.rstrip('/')}/models")
                resp.raise_for_status()
                data = resp.json()
                models = [m["id"] for m in data.get("data", [])]
                return {"models": models}
        except Exception as e:
            return {"models": [], "error": str(e)}

    if provider == "openrouter":
        try:
            api_key = req.api_key or config.get("openrouter.api_key") or ""
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{host.rstrip('/')}/models", headers=headers)
                resp.raise_for_status()
                data = resp.json()
                models = [m["id"] for m in data.get("data", [])]
                return {"models": models}
        except Exception as e:
            return {"models": [], "error": str(e)}

    return {"models": [], "error": f"Unknown provider: {provider}"}


class ProviderTestRequest(BaseModel):
    provider: str
    host: str
    model: str | None = None
    api_key: str | None = None


@app.post("/api/providers/test")
async def test_provider(req: ProviderTestRequest, project: str | None = None):
    """Test connection to a provider."""
    config = _config_for(project)
    provider = req.provider.lower()
    host = req.host
    model = req.model
    api_key = req.api_key

    start = time.time()

    if provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{host.rstrip('/')}/api/tags")
                resp.raise_for_status()
                if model:
                    # Check if model exists
                    data = resp.json()
                    models = [m["name"] for m in data.get("models", [])]
                    if model not in models:
                        return {"ok": False, "error": f"Model '{model}' not found. Available: {', '.join(models[:5])}..."}
                latency = int((time.time() - start) * 1000)
                return {"ok": True, "latency_ms": latency}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if provider == "lmstudio":
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{host.rstrip('/')}/models")
                resp.raise_for_status()
                if model:
                    data = resp.json()
                    models = [m["id"] for m in data.get("data", [])]
                    if model not in models:
                        return {"ok": False, "error": f"Model '{model}' not found. Available: {', '.join(models[:5])}..."}
                latency = int((time.time() - start) * 1000)
                return {"ok": True, "latency_ms": latency}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if provider == "openrouter":
        try:
            key = api_key or config.get("openrouter.api_key") or ""
            if not key:
                return {"ok": False, "error": "OpenRouter API key not set"}
            headers = {"Authorization": f"Bearer {key}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{host.rstrip('/')}/models", headers=headers)
                resp.raise_for_status()
                if model:
                    data = resp.json()
                    models = [m["id"] for m in data.get("data", [])]
                    if model not in models:
                        return {"ok": False, "error": f"Model '{model}' not found or not accessible"}
                latency = int((time.time() - start) * 1000)
                return {"ok": True, "latency_ms": latency}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return {"ok": False, "error": f"Unknown provider: {provider}"}


@app.post("/api/providers/select")
async def select_provider(req: SelectProviderRequest, project: str | None = None):
    config = _config_for(project)
    config.save_overrides({"gateway": {"provider": req.provider}})
    return {"provider": req.provider}


@app.get("/api/settings")
async def get_settings(project: str | None = None):
    """
    Returns the full editable configuration for the Settings panel.
    openrouter.api_key is never echoed back in full -- only whether one is
    set -- so a stored key can't leak back out through this endpoint.
    """
    config = _config_for(project)
    openrouter = dict(config.data.get("openrouter", {}))
    has_key = bool(openrouter.pop("api_key", ""))
    return {
        "gateway": config.data.get("gateway", {}),
        "ollama": config.data.get("ollama", {}),
        "lmstudio": config.data.get("lmstudio", {}),
        "openrouter": {**openrouter, "api_key_set": has_key},
    }


@app.post("/api/settings")
async def update_settings(update: SettingsUpdate, project: str | None = None):
    """
    Persists manual provider/model/host/api_key edits from the desktop
    Settings panel to .igris/config.yaml via Config.save_overrides, so
    they survive a restart -- unlike the old in-memory-only behavior.
    An empty api_key field is treated as "leave unchanged", not "clear it",
    since the panel never receives the real key back to redisplay.
    """
    config = _config_for(project)
    updates: dict = {}

    if update.provider:
        updates["gateway"] = {"provider": update.provider}

    for section_name, section in (
        ("ollama", update.ollama),
        ("lmstudio", update.lmstudio),
        ("openrouter", update.openrouter),
    ):
        if section is None:
            continue
        section_updates = section.model_dump(exclude_none=True)
        if section_name == "openrouter" and not section_updates.get("api_key"):
            section_updates.pop("api_key", None)
        if section_updates:
            updates[section_name] = section_updates

    if updates:
        config.save_overrides(updates)

    return await get_settings(project=project)


@app.get("/api/mcp/tools")
async def list_mcp_tools(project: str | None = None):
    config = _config_for(project)
    async with MCPManager(config) as mcp:
        return {"tools": [h.replace("__", ".") for h in mcp._tools.keys()]}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Non-streaming fallback -- runs the full loop and returns the final result."""
    config = _config_for(req.project)
    memory = Memory(config)
    context_engine = ContextEngine(config, memory)
    llm = build_llm(config)
    intent_resolver = IntentResolver(config, llm=llm)
    skills = SkillLoader(config)

    async with MCPManager(config) as mcp:
        loop = RepromptLoop(config, llm, mcp, skills, context_engine, intent_resolver, memory)
        result = await loop.run(req.message)

    provider = config.get("gateway.provider", "ollama")
    return {
        "response": result.final_response,
        "needs_clarification": result.needs_clarification,
        "clarifying_question": result.clarifying_question,
        "iterations": result.iterations,
        "trace": [{"stage": s, "detail": d} for s, d in result.trace],
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "cost_usd": estimate_cost_usd(provider, result.prompt_tokens, result.completion_tokens, config),
    }


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    """
    Streaming variant: client sends {"message": "...", "project": "..."},
    server pushes one JSON event per pipeline stage as it happens
    ({"type":"stage","stage":...,"detail":...}), then a final event
    ({"type":"final", "response":..., "needs_clarification":..., ...}).
    Powers the UI's live Runtime/Loop/Logs panel.
    """
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            message = payload.get("message", "")
            project = payload.get("project")

            try:
                config = _config_for(project)
            except ValueError as e:
                await websocket.send_json({"type": "error", "detail": str(e)})
                continue

            memory = Memory(config)
            context_engine = ContextEngine(config, memory)
            llm = build_llm(config)
            intent_resolver = IntentResolver(config, llm=llm)
            skills = SkillLoader(config)

            async def on_stage(stage: str, detail: str, ws=websocket):
                await ws.send_json({"type": "stage", "stage": stage, "detail": detail})

            async def on_preview(result, ws=websocket):
                await ws.send_json({
                    "type": "preview",
                    "tester_name": result.tester_name,
                    "success": result.success,
                    "summary": result.summary,
                    "details": result.details,
                    "errors": result.errors,
                    "artifacts": result.artifacts,
                })

            async with MCPManager(config) as mcp:
                loop = RepromptLoop(config, llm, mcp, skills, context_engine, intent_resolver, memory)
                result = await loop.run(message, on_stage=on_stage, on_preview=on_preview)

            provider = config.get("gateway.provider", "ollama")
            await websocket.send_json({
                "type": "final",
                "response": result.final_response,
                "needs_clarification": result.needs_clarification,
                "clarifying_question": result.clarifying_question,
                "iterations": result.iterations,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "cost_usd": estimate_cost_usd(provider, result.prompt_tokens, result.completion_tokens, config),
            })
    except WebSocketDisconnect:
        pass
