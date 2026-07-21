"""
Tests for igris.server. Uses FastAPI's TestClient (sync wrapper over
httpx) so no real server process is needed. The active LLM provider is
monkeypatched to MockLLM so no live Ollama/LM Studio/OpenRouter is
required. workspace_root is redirected to an isolated tmp_path so tests
never touch the real igris-cli/projects/ directory.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris import workspace as ws
from mock_llm import MockLLM


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ws, "workspace_root", lambda: tmp_path)

    import igris.server as server_module
    monkeypatch.setattr(server_module, "build_llm", lambda config: MockLLM(
        chat_responses=["PASS\nlooks good"],
        run_responses=["mock response from server test"],
        chat_tokens=[(30, 8)],
        run_tokens=[(200, 40)],
    ))

    from fastapi.testclient import TestClient
    return TestClient(server_module.app)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_and_list_projects(client):
    resp = client.post("/api/projects", json={"name": "demo"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "demo"

    resp = client.get("/api/projects")
    assert resp.status_code == 200
    body = resp.json()
    assert "demo" in body["projects"]
    assert body["active"] == "demo"


def test_activate_project(client):
    client.post("/api/projects", json={"name": "a"})
    client.post("/api/projects", json={"name": "b"})

    resp = client.post("/api/projects/a/activate")
    assert resp.json()["active"] == "a"

    resp = client.get("/api/projects")
    assert resp.json()["active"] == "a"


def test_activate_nonexistent_project_errors(client):
    resp = client.post("/api/projects/does-not-exist/activate")
    assert "error" in resp.json()


def test_list_skills_for_project(client):
    client.post("/api/projects", json={"name": "demo"})
    resp = client.get("/api/skills", params={"project": "demo"})
    assert resp.status_code == 200
    names = {s["name"] for s in resp.json()["skills"]}
    assert "intent-resolver" in names
    assert "quality-reviewer" in names


def test_list_providers(client):
    resp = client.get("/api/providers")
    assert resp.status_code == 200
    assert set(resp.json()["providers"]) == {"ollama", "lmstudio", "openrouter"}


def test_select_provider_persists(client):
    client.post("/api/projects", json={"name": "demo"})
    resp = client.post("/api/providers/select", params={"project": "demo"}, json={"provider": "lmstudio"})
    assert resp.json()["provider"] == "lmstudio"

    resp = client.get("/api/settings", params={"project": "demo"})
    assert resp.json()["gateway"]["provider"] == "lmstudio"


def test_get_settings_shape(client):
    client.post("/api/projects", json={"name": "demo"})
    resp = client.get("/api/settings", params={"project": "demo"})
    body = resp.json()
    assert "ollama" in body and "model" in body["ollama"]
    assert "lmstudio" in body and "host" in body["lmstudio"]
    assert "openrouter" in body
    assert "api_key" not in body["openrouter"]  # never echoed back
    assert body["openrouter"]["api_key_set"] is False


def test_update_settings_persists_model_and_host(client):
    client.post("/api/projects", json={"name": "demo"})
    resp = client.post(
        "/api/settings",
        params={"project": "demo"},
        json={"ollama": {"model": "qwen2.5-coder:7b", "host": "http://localhost:11500"}},
    )
    assert resp.status_code == 200
    assert resp.json()["ollama"]["model"] == "qwen2.5-coder:7b"
    assert resp.json()["ollama"]["host"] == "http://localhost:11500"

    # persisted across a fresh read, not just the response echo
    resp2 = client.get("/api/settings", params={"project": "demo"})
    assert resp2.json()["ollama"]["model"] == "qwen2.5-coder:7b"


def test_update_settings_api_key_sets_flag_without_echoing_it(client):
    client.post("/api/projects", json={"name": "demo"})
    resp = client.post(
        "/api/settings",
        params={"project": "demo"},
        json={"provider": "openrouter", "openrouter": {"api_key": "sk-secret-123", "model": "openrouter/auto"}},
    )
    body = resp.json()
    assert body["gateway"]["provider"] == "openrouter"
    assert body["openrouter"]["api_key_set"] is True
    assert "sk-secret-123" not in str(body)  # key itself never comes back


def test_update_settings_empty_api_key_does_not_clear_existing_key(client):
    client.post("/api/projects", json={"name": "demo"})
    client.post(
        "/api/settings",
        params={"project": "demo"},
        json={"openrouter": {"api_key": "sk-secret-123"}},
    )
    # posting a model change without api_key should not wipe the stored key
    client.post(
        "/api/settings",
        params={"project": "demo"},
        json={"openrouter": {"model": "openrouter/auto"}},
    )
    resp = client.get("/api/settings", params={"project": "demo"})
    assert resp.json()["openrouter"]["api_key_set"] is True


def test_chat_endpoint_runs_full_loop(client):
    client.post("/api/projects", json={"name": "demo"})
    resp = client.post("/api/chat", json={"message": "list files in this directory", "project": "demo"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["needs_clarification"] is False
    assert "mock response" in body["response"]
    assert len(body["trace"]) > 0


def test_chat_endpoint_reports_token_usage_and_cost(client):
    client.post("/api/projects", json={"name": "demo"})
    resp = client.post("/api/chat", json={"message": "list files in this directory", "project": "demo"})
    body = resp.json()
    assert body["prompt_tokens"] == 200 + 30  # run_with_tools + self-review
    assert body["completion_tokens"] == 40 + 8
    assert body["cost_usd"] == 0.0  # default provider is ollama -- always free


def test_chat_endpoint_clarification_path(client):
    client.post("/api/projects", json={"name": "demo"})
    resp = client.post("/api/chat", json={"message": "hmm", "project": "demo"})
    body = resp.json()
    assert body["needs_clarification"] is True
    assert body["clarifying_question"]


def test_ws_chat_streams_stage_events_then_final(client):
    client.post("/api/projects", json={"name": "demo"})
    with client.websocket_connect("/ws/chat") as ws_conn:
        ws_conn.send_json({"message": "list files in this directory", "project": "demo"})

        events = []
        while True:
            event = ws_conn.receive_json()
            events.append(event)
            if event["type"] == "final":
                break

        stage_events = [e for e in events if e["type"] == "stage"]
        final_events = [e for e in events if e["type"] == "final"]

        assert len(stage_events) >= 5  # snapshot, intent, complexity, loop_plan, skills, gather, spec, attempt_1...
        assert len(final_events) == 1
        assert "mock response" in final_events[0]["response"]
        assert final_events[0]["prompt_tokens"] == 200 + 30
        assert final_events[0]["completion_tokens"] == 40 + 8
        assert final_events[0]["cost_usd"] == 0.0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
