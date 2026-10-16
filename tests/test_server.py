import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from property_agent import agent as agent_module
from property_agent import server


class FakeMessages:
    """Replies with a tool call on the first request, then text."""

    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        last = kwargs["messages"][-1]
        if isinstance(last["content"], str) and "save me" in last["content"]:
            return SimpleNamespace(stop_reason="tool_use", content=[SimpleNamespace(
                type="tool_use", id="t1", name="save_lead",
                input={"name": "Tan", "phone": "91234567", "summary": "HDB upgrader"})])
        if isinstance(last["content"], list):
            return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Saved, the agent will call you.")])
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Hello from the advisor")])


@pytest.fixture
def api(monkeypatch, tmp_path):
    fake = FakeMessages()
    monkeypatch.setattr(server, "_client", SimpleNamespace(beta=SimpleNamespace(messages=fake)))
    monkeypatch.setattr(agent_module, "LEADS_FILE", str(tmp_path / "leads.jsonl"))
    monkeypatch.setattr(server, "ADMIN_TOKEN", "secret")
    server._sessions.clear()
    server._hits.clear()
    return TestClient(server.app), fake


def test_chat_keeps_session(api):
    client, fake = api
    r = client.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 200 and r.json()["reply"] == "Hello from the advisor"
    sid = r.json()["session_id"]
    r2 = client.post("/api/chat", json={"session_id": sid, "message": "more"})
    assert r2.json()["session_id"] == sid
    # history list (shared by reference): greeting (2) + hi/reply (2) + more/reply (2)
    assert len(fake.calls[-1]["messages"]) == 6


def test_lead_capture_and_admin(api):
    client, _ = api
    r = client.post("/api/chat", json={"message": "please save me"})
    assert "agent will call" in r.json()["reply"]
    assert client.get("/admin/leads?token=wrong").status_code == 404
    leads = client.get("/admin/leads?token=secret").json()
    assert leads[0]["name"] == "Tan" and leads[0]["phone"] == "91234567"


def test_rate_limit_and_validation(api):
    client, _ = api
    assert client.post("/api/chat", json={"message": ""}).status_code == 422
    assert client.post("/api/chat", json={"message": "x" * 5000}).status_code == 422
    codes = [client.post("/api/chat", json={"message": "hi"}).status_code for _ in range(server.RATE_LIMIT_PER_IP + 1)]
    assert codes[-1] == 429


def test_widget_and_demo_served(api):
    client, _ = api
    assert "attachShadow" in client.get("/widget.js").text
    assert "/widget.js" in client.get("/").text
    assert client.get("/api/config").json()["agent_name"]


def test_lead_webhook_forwarding(monkeypatch, tmp_path):
    sent = []

    class Resp:
        def close(self):
            pass

    def fake_urlopen(req, timeout):
        sent.append(json.loads(req.data))
        return Resp()

    monkeypatch.setattr(agent_module, "LEADS_FILE", str(tmp_path / "leads.jsonl"))
    monkeypatch.setattr(agent_module, "LEAD_WEBHOOK_URL", "https://example.invalid/hook")
    monkeypatch.setattr(agent_module.urllib.request, "urlopen", fake_urlopen)
    agent_module.save_lead({"name": "Lim", "phone": "98765432", "summary": "First-timer"})
    assert sent[0]["name"] == "Lim"

    def broken(req, timeout):
        raise OSError("down")

    monkeypatch.setattr(agent_module.urllib.request, "urlopen", broken)
    assert agent_module.save_lead({"name": "Ng", "phone": "9", "summary": "x"})["saved"]
