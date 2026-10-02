from dataclasses import dataclass
from pathlib import Path
import os
import re
import sys

from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task, LLM

from src.verify import verify_report, get_verdict


ROOT = Path(__file__).resolve().parents[1]
INTENT_PATH = ROOT / "intent" / "current-feature.md"
OUTPUT_PATH = ROOT / "output" / "final_report.md"
DEFAULT_MODEL = "anthropic/claude-sonnet-5-5"

# Every task starts with this rule. The intent says what must be true; the crew does no more than that,
# and an assumption stays a labelled, reversible note instead of quietly becoming architecture.
SCOPE_RULE = (
    "RULE: Choose the simplest implementation that satisfies the intent. "
    "When an assumption is necessary, make it visible and reversible. "
    "Do not turn an assumption into architecture unless the intent or repository evidence requires it."
)
# Shorter outputs keep runs fast: each task reads every earlier task's output.
WORD_BUDGETS = {"analysis": 300, "architecture": 350, "implementation": 450, "report": 1200}


def read_intent() -> str:
    if not INTENT_PATH.exists():
        raise FileNotFoundError(f"Intent file not found: {INTENT_PATH}")
    return INTENT_PATH.read_text(encoding="utf-8")


def clean_output(text: str) -> str:
    """Strip a single wrapping ```markdown fence if the model added one."""
    text = text.strip()
    match = re.fullmatch(r"```(?:markdown|md)?\s*\n(.*)\n```", text, re.DOTALL)
    return (match.group(1) if match else text).strip() + "\n"


def build_crew(intent_text: str) -> Crew:
    model_name = os.getenv("MODEL", DEFAULT_MODEL)
    # No temperature: current Claude models reject it with a 400.
    llm = LLM(model=model_name)

    # Agent-role over-writing: earlier prompts asked each role for a full menu (tech choices,
    # failure modes, future verification points) and the agents produced an enterprise
    # blueprint every time, which also made runs slow. Each role now does only what the
    # intent needs, and every proposal must trace back to a numbered requirement.
    requirements_analyst = Agent(
        role="Requirements Analyst",
        goal="State only the requirements the intent actually makes, each one testable and traceable to the intent text.",
        backstory=(
            "You are a senior analyst. You preserve the user's intent exactly. You never add a "
            "requirement the intent does not state or clearly imply, and you name ambiguity instead "
            "of resolving it with your own preferences."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    solution_architect = Agent(
        role="Solution Architect",
        goal=(
            "Determine the simplest architecture that satisfies the intent and the context it provides. "
            "Do not introduce components, abstractions, or infrastructure unless they solve a stated requirement."
        ),
        backstory=(
            "You are a pragmatic architect who is judged by what you leave out. A component that no "
            "requirement needs is a defect in your design, not extra value."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    developer = Agent(
        role="Developer",
        goal=(
            "Plan only what is necessary to implement the chosen architecture. Prefer the conventions and "
            "existing capabilities the intent names. Do not create scaffolding solely because it is a general best practice."
        ),
        backstory=(
            "You are a senior developer who ships the smallest working thing. You cannot see a repository, "
            "so you do not invent one; you plan the fewest files and steps that meet the requirements."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    reviewer = Agent(
        role="Intent Reviewer",
        goal="Check the proposal against the original intent for both gaps and over-building.",
        backstory=(
            "You are an independent reviewer. Missing something the intent asks for is a failure, and so "
            "is adding something it does not ask for. You report both plainly."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    analyze_task = Task(
        description=f"""
{SCOPE_RULE}

Read the intent below and list the engineering requirements it actually makes.

- Number each requirement R1, R2, ... and quote or cite the intent line it comes from.
- Do not add requirements the intent does not state or clearly imply. No "nice to have" items.
- List assumptions separately, numbered A1, A2, ... Make an assumption only where the intent leaves a gap you must fill.
  For each one, say what would change if it turned out wrong, so it can be reversed.
- List open questions separately. Do not resolve them with your own preferences.
- Turn the intent's success criteria into acceptance checks.
- Stay under {WORD_BUDGETS["analysis"]} words.

INTENT:
{intent_text}
""",
        expected_output=(
            "A short Markdown list of numbered requirements (R1, R2, ...) each traced to the intent, "
            "then numbered assumptions (A1, A2, ...) each with what changes if it is wrong, open questions, and acceptance checks."
        ),
        agent=requirements_analyst,
    )

    architecture_task = Task(
        description=f"""
{SCOPE_RULE}

Using only the numbered requirements from the previous task, determine the simplest architecture that satisfies them.

- Do not introduce components, abstractions, or infrastructure unless they solve a stated requirement.
- For every component, name the requirement(s) it serves (e.g. "serves R2"). If you cannot, leave it out.
- Do not turn an assumption into architecture. A component that exists only because of an assumption (A1, A2, ...)
  is left out unless the intent requires it; if a choice depends on an assumption, cite it ("depends on A1")
  and keep it easy to change.
- Describe the API shape only as far as the requirements need.
- If you consider something and reject it as unnecessary, say so in one line. Do not design it.
- Stay inside the intent's boundaries. Stay under {WORD_BUDGETS["architecture"]} words.
""",
        expected_output="A short Markdown architecture in which every component cites the requirement it serves.",
        agent=solution_architect,
        context=[analyze_task],
    )

    implementation_task = Task(
        description=f"""
{SCOPE_RULE}

Plan only what is necessary to implement the chosen architecture.

- Give the smallest file structure and the fewest steps that meet the requirements; each step cites the requirement it serves.
- Prefer the conventions and existing capabilities the intent names. Do not create scaffolding solely because it is a general best practice.
- Where a step depends on an assumption, cite it ("depends on A2") and keep that step reversible. Do not plan work that only an assumption justifies.
- Testing: only the tests that prove the acceptance checks.
- Anything you think is valuable but no requirement needs goes in one line under "Beyond the intent (needs human approval)". Do not plan it.
- Do not build the application. Stay under {WORD_BUDGETS["implementation"]} words.
""",
        expected_output="A short Markdown implementation plan in which every step cites the requirement it serves.",
        agent=developer,
        context=[analyze_task, architecture_task],
    )

    review_task = Task(
        description=f"""
{SCOPE_RULE}

Review all prior work against the ORIGINAL intent below. Carry forward only what traces to a requirement;
condense, do not expand. Keep the whole report under {WORD_BUDGETS["report"]} words.

Produce the final report with these exact sections:

# Final Engineering Recommendation
## 1. Interpreted Requirements
## 2. Architecture
## 3. API Design
## 4. Implementation Approach
## 5. Testing Strategy
## 6. Risks and Assumptions
## 7. Intent Compliance Review

In the Intent Compliance Review, explicitly state whether each major output and success criterion was addressed.
If something is missing, say so rather than pretending it is complete.
In Risks and Assumptions, list every assumption (A1, A2, ...) with what changes if it is wrong.
Also include a scope check: list anything in the proposal that the intent did not ask for,
and any assumption that was turned into architecture without the intent requiring it.
A proposal that adds components, scaffolding, or infrastructure no requirement needs cannot be PASS.
End the Intent Compliance Review with exactly one line in this form:
**Verdict:** PASS | PARTIAL | FAIL
Output raw Markdown only. Do not wrap the report in a code fence.

ORIGINAL INTENT:
{intent_text}
""",
        expected_output="A complete final Markdown report matching the required section structure.",
        agent=reviewer,
        context=[analyze_task, architecture_task, implementation_task],
    )

    return Crew(
        agents=[requirements_analyst, solution_architect, developer, reviewer],
        tasks=[analyze_task, architecture_task, implementation_task, review_task],
        process=Process.sequential,
        verbose=True,
    )


@dataclass
class RunResult:
    report: str
    errors: list[str]
    verdict: str | None

    @property
    def passed(self) -> bool:
        return not self.errors


def require_api_key() -> None:
    """Fail before any agent work starts, so a missing key never looks like a crew failure."""
    load_dotenv(ROOT / ".env")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
        )


def run_crew(intent_text: str) -> RunResult:
    """Run the crew on one intent, write the report, and verify it.

    Shared by the CLI and the web server so both go through the same
    deterministic gate; callers decide how to surface a failed check.
    """
    crew = build_crew(intent_text)
    result = crew.kickoff()

    report = clean_output(result.raw)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(report, encoding="utf-8")

    # Systems verify: deterministic gate, independent of the Reviewer agent.
    return RunResult(report=report, errors=verify_report(report), verdict=get_verdict(report))


def main() -> None:
    require_api_key()
    outcome = run_crew(read_intent())
    report = outcome.report

    print("\nCrew complete.")
    print(f"Final report written to: {OUTPUT_PATH}")

    errors = outcome.errors
    if errors:
        print("VERIFICATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print(f"VERIFICATION PASSED (reviewer verdict: {get_verdict(report)})")


if __name__ == "__main__":
    main()
