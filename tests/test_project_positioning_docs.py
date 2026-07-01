from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DEMO_DOC = ROOT / "docs" / "local-mvp-demo.md"


def test_readme_has_resume_friendly_project_positioning():
    readme = README.read_text(encoding="utf-8")

    assert "## What This Project Demonstrates" in readme
    assert "## Quick Local Demo" in readme
    assert "docs/local-mvp-demo.md" in readme
    for phrase in [
        "FastAPI control plane",
        "Kubernetes Python API client",
        "Redis-backed run state",
        "human-approved execution plans",
        "Docker Compose",
        "GitHub Actions",
    ]:
        assert phrase in readme


def test_local_mvp_demo_walkthrough_covers_safe_and_live_paths():
    demo = DEMO_DOC.read_text(encoding="utf-8")

    for heading in [
        "# Local MVP Demo Walkthrough",
        "## What You Are Demonstrating",
        "## Safe Demo Path",
        "## Live Kubernetes Path",
        "## Interview Talking Points",
    ]:
        assert heading in demo

    for command in [
        "docker compose up --build",
        "python scripts/smoke_check.py",
        "python scripts/local_demo.py --plan-only",
        "http://localhost:8000/approvals/dashboard",
        ".\\scripts\\start-local-dev.ps1",
        "python scripts/local_demo.py",
    ]:
        assert command in demo

    assert "/runs" in demo
    assert "does not shell out to `kubectl`" in demo
