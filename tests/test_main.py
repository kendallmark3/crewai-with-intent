"""Offline tests: build the crew without calling the API."""
import pytest
from crewai import Process

from src import main as app


def test_intent_file_is_readable():
    text = app.read_intent()
    assert "## Success Criteria" in text and "## Boundaries" in text


def test_default_model_is_current():
    assert app.DEFAULT_MODEL == "anthropic/claude-sonnet-5-5"


def test_crew_shape(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-offline")
    crew = app.build_crew("TEST INTENT")
    roles = [a.role for a in crew.agents]
    assert roles == ["Requirements Analyst", "Solution Architect", "Developer", "Intent Reviewer"]
    assert crew.process == Process.sequential
    assert all(a.allow_delegation is False for a in crew.agents)

    analyze, arch, impl, review = crew.tasks
    assert arch.context == [analyze]
    assert impl.context == [analyze, arch]
    assert review.context == [analyze, arch, impl]
    assert "TEST INTENT" in analyze.description and "TEST INTENT" in review.description
    assert "**Verdict:**" in review.description


def test_clean_output_strips_fence():
    assert app.clean_output("```markdown\n# Hi\n```") == "# Hi\n"
    assert app.clean_output("# Hi") == "# Hi\n"


def test_missing_api_key_fails_fast(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(app, "load_dotenv", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        app.main()
