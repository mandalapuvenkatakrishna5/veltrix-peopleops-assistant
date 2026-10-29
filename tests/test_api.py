from fastapi.testclient import TestClient
import app.main as main

def test_health_and_auth_contract(monkeypatch):
    # Keep repository tests runnable without committing the assessment data folder.
    monkeypatch.setattr(main, "ingest", lambda: [{"doc_id":"TEST","text":"test","locator":"p. 1","regions":["GLOBAL"],"effective_date":"2020-01-01","access_level":"all","doc_type":"policy"}])
    monkeypatch.setattr(main, "employee", lambda employee_id: None)
    with TestClient(main.app) as client:
        health=client.get("/health")
        assert health.status_code==200
        r=client.post("/chat",headers={"X-Employee-Id":"NOT_REAL"},json={"session_id":"test","message":"hello"})
        assert r.status_code==401
