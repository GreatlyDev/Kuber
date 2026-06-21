from fastapi.testclient import TestClient

from devassist_api.main import app


def test_serves_local_approval_dashboard_page():
    client = TestClient(app)

    response = client.get("/approvals/dashboard")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>DevAssist Approvals</title>" in response.text
    assert 'id="approval-list"' in response.text
    assert 'href="/assets/approval-dashboard.css"' in response.text
    assert 'src="/assets/approval-dashboard.js"' in response.text


def test_serves_approval_dashboard_javascript_without_execution_calls():
    client = TestClient(app)

    response = client.get("/assets/approval-dashboard.js")

    assert response.status_code == 200
    assert "loadPendingApprovals" in response.text
    assert 'fetch("/approvals/pending?limit=25")' in response.text
    assert "approve`" in response.text
    assert "reject`" in response.text
    assert "/runs" not in response.text
    assert "kubectl" not in response.text.lower()


def test_serves_approval_dashboard_stylesheet():
    client = TestClient(app)

    response = client.get("/assets/approval-dashboard.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert ".approval-list" in response.text
