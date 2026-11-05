import json
import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from app.main import create_app

KEY = "a" * 64

@pytest.fixture
def lab(tmp_path):
    key = tmp_path / "key"
    key.write_text(KEY)
    log = tmp_path / "api.jsonl"
    db = "sqlite:///" + str(tmp_path / "tasks.db")
    app = create_app(db, key, log)
    with TestClient(app) as client:
        yield client, key, log, app, db

def headers(key=KEY):
    return {"X-API-Key": key}

def test_health_and_home(lab):
    client, *_ = lab
    assert client.get("/health/live").json()["status"] == "alive"
    assert client.get("/health/ready").status_code == 200
    assert "Operations board" in client.get("/").text
    assert client.get("/docs").status_code == 404

def test_authentication(lab):
    client, *_ = lab
    assert client.get("/api/tasks").status_code == 401
    assert client.get("/api/tasks", headers=headers("wrong")).status_code == 401

def test_crud(lab):
    client, *_ = lab
    response = client.post("/api/tasks", json={"title": "  restore drill  "}, headers=headers())
    assert response.status_code == 201
    task = response.json()
    assert task["title"] == "restore drill" and task["done"] is False
    assert task in client.get("/api/tasks", headers=headers()).json()
    path = "/api/tasks/" + task["id"]
    assert client.patch(path, json={"done": True}, headers=headers()).json()["done"] is True
    assert client.delete(path, headers=headers()).status_code == 204
    assert client.delete(path, headers=headers()).status_code == 404

@pytest.mark.parametrize("payload", [{"title": ""}, {"title": "   "}, {"title": "x"*121}, {"title": "ok", "owner": "other"}, {}])
def test_reject_invalid_payloads(lab, payload):
    assert lab[0].post("/api/tasks", json=payload, headers=headers()).status_code == 422

@pytest.mark.parametrize("limit", [0, 101, "bad"])
def test_bounded_pagination(lab, limit):
    assert lab[0].get(f"/api/tasks?limit={limit}", headers=headers()).status_code == 422

def test_ids(lab):
    client, *_ = lab
    assert client.delete("/api/tasks/invalid", headers=headers()).status_code == 422
    assert client.patch("/api/tasks/"+str(uuid.uuid4()), json={"done": True}, headers=headers()).status_code == 404

def test_live_key_rotation(lab):
    client, key, *_ = lab
    key.write_text("b"*64)
    assert client.get("/api/tasks", headers=headers()).status_code == 401
    assert client.get("/api/tasks", headers=headers("b"*64)).status_code == 200

@pytest.mark.parametrize("broken", ["missing", "short"])
def test_missing_secret_fails_closed(lab, broken):
    client, key, *_ = lab
    if broken == "missing": key.unlink()
    else: key.write_text("short")
    assert client.get("/api/tasks", headers=headers()).status_code == 503
    assert client.get("/health/ready").status_code == 503
    assert client.get("/health/live").status_code == 200

def test_sql_literal_is_data(lab):
    client, *_ = lab
    title = "'); DROP TABLE tasks; --"
    assert client.post("/api/tasks", json={"title": title}, headers=headers()).status_code == 201
    assert client.get("/api/tasks", headers=headers()).json()[0]["title"] == title

def test_logs_redact_payloads_queries_and_credentials(lab):
    client, _, log, *_ = lab
    client.post("/api/tasks?secret=do-not-log", json={"title": "private title"}, headers=headers())
    content = log.read_text()
    for secret in (KEY, "private title", "do-not-log", "X-API-Key"):
        assert secret not in content
    rows = [json.loads(line) for line in content.splitlines()]
    assert rows[-1]["route"] == "/api/tasks" and rows[-1]["status"] == 201

def test_metric_cardinality_and_request_id(lab):
    client, *_ = lab
    task_id = str(uuid.uuid4())
    result = client.delete("/api/tasks/"+task_id, headers=headers() | {"X-Request-ID":"request-123"})
    assert result.headers["x-request-id"] == "request-123"
    metrics = client.get("/metrics").text
    assert 'route="/api/tasks/{task_id}"' in metrics
    assert task_id not in metrics
    assert "atlasops_http_request_duration_seconds_bucket" in metrics

def test_database_error_is_sanitized(lab, monkeypatch):
    client, _, _, app, _ = lab
    def broken():
        raise OperationalError("SELECT private", {}, RuntimeError("password=DO_NOT_EXPOSE"))
    monkeypatch.setattr(app.state.engine, "connect", broken)
    result = client.get("/health/ready")
    assert result.status_code == 503
    assert "DO_NOT_EXPOSE" not in result.text
    assert client.get("/health/live").status_code == 200

def test_persistence_across_app_instances(lab, tmp_path):
    client, key, _, _, db = lab
    task = client.post("/api/tasks", json={"title":"persistent"}, headers=headers()).json()
    with TestClient(create_app(db, key, tmp_path / "second.log")) as second:
        assert task in second.get("/api/tasks", headers=headers()).json()

@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="Requires a PostgreSQL server (CI service)")
def test_postgresql_roundtrip(tmp_path):
    key = tmp_path / "key"; key.write_text(KEY)
    with TestClient(create_app(os.environ["TEST_POSTGRES_URL"], key)) as client:
        response = client.post("/api/tasks", json={"title":"PostgreSQL integration"}, headers=headers())
        assert response.status_code == 201
        task = response.json()
        assert task in client.get("/api/tasks?limit=100", headers=headers()).json()
        assert client.delete("/api/tasks/" + task["id"], headers=headers()).status_code == 204
