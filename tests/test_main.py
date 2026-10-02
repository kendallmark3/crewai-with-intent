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
    assert all(a.llm.temperature is None for a in crew.agents)

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


def test_run_crew_writes_and_verifies_report(monkeypatch, tmp_path):
    class FakeCrew:
        def kickoff(self):
            return type("Out", (), {"raw": "```markdown\n# Not the right title\n```"})()

    out = tmp_path / "final_report.md"
    monkeypatch.setattr(app, "OUTPUT_PATH", out)
    monkeypatch.setattr(app, "build_crew", lambda intent: FakeCrew())
    result = app.run_crew("PASTED INTENT")
    assert out.read_text() == "# Not the right title\n"
    assert result.report == "# Not the right title\n"
    assert not result.passed and result.verdict is None
    assert any("Missing title" in e for e in result.errors)


def test_every_task_carries_the_minimal_scope_rule(monkeypatch):
    """Guards against agent-role over-writing: each role must get the simplest-implementation and assumption rules."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-offline")
    analyze, arch, impl, review = app.build_crew("TEST INTENT").tasks
    for task in (analyze, arch, impl, review):
        assert app.SCOPE_RULE in task.description
    assert "Do not add requirements the intent does not state" in analyze.description
    assert "Do not introduce components, abstractions, or infrastructure unless they solve a stated requirement" in arch.description
    assert "Do not create scaffolding solely because it is a general best practice" in impl.description
    assert "Beyond the intent (needs human approval)" in impl.description
    assert "cannot be PASS" in review.description
    assert "make it visible and reversible" in app.SCOPE_RULE
    assert "Do not turn an assumption into architecture" in app.SCOPE_RULE
    assert "numbered A1, A2" in analyze.description
    assert "Do not turn an assumption into architecture" in arch.description
    assert "Do not plan work that only an assumption justifies" in impl.description
    assert "assumption that was turned into architecture" in review.description


def test_word_budgets_are_in_the_prompts(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-offline")
    analyze, arch, impl, review = app.build_crew("TEST INTENT").tasks
    budgets = app.WORD_BUDGETS
    assert f"under {budgets['analysis']} words" in analyze.description
    assert f"under {budgets['architecture']} words" in arch.description
    assert f"under {budgets['implementation']} words" in impl.description
    assert f"under {budgets['report']} words" in review.description
