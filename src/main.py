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

    requirements_analyst = Agent(
        role="Requirements Analyst",
        goal="Translate the human-authored intent into precise, testable engineering requirements.",
        backstory=(
            "You are a senior business and systems analyst. You preserve the user's intent, "
            "surface ambiguity, and avoid inventing unnecessary scope."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    solution_architect = Agent(
        role="Solution Architect",
        goal="Create the simplest architecture that satisfies the interpreted requirements and boundaries.",
        backstory=(
            "You are a pragmatic software architect. You optimize for clarity, maintainability, "
            "and explicit tradeoffs rather than unnecessary complexity."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    developer = Agent(
        role="Developer",
        goal="Turn the architecture into a concrete implementation approach a developer could execute.",
        backstory=(
            "You are a senior developer. You convert architecture into practical file structures, "
            "interfaces, implementation steps, and tests."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    reviewer = Agent(
        role="Intent Reviewer",
        goal="Review the proposed solution against the original intent and identify gaps before approval.",
        backstory=(
            "You are an independent engineering reviewer. You compare outputs directly against "
            "the source intent, boundaries, outputs, and success criteria."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    analyze_task = Task(
        description=f"""
Read the following intent and convert it into a concise set of engineering requirements.

Do not expand the scope beyond what the intent asks for.
Call out assumptions separately.

INTENT:
{intent_text}
""",
        expected_output=(
            "A Markdown requirements analysis containing functional requirements, non-functional "
            "requirements, constraints, assumptions, and explicit acceptance checks."
        ),
        agent=requirements_analyst,
    )

    architecture_task = Task(
        description="""
Using the requirements analysis from the previous task, propose the simplest complete architecture.

Include:
- components
- responsibilities
- data flow
- API shape
- suggested technology choices
- tradeoffs
- where deterministic verification should eventually be inserted

Stay inside the original intent boundaries.
""",
        expected_output="A concise Markdown architecture proposal.",
        agent=solution_architect,
        context=[analyze_task],
    )

    implementation_task = Task(
        description="""
Using the requirements and architecture, create a practical implementation plan.

Include:
- proposed project/file structure
- important interfaces or example request/response shapes
- step-by-step build sequence
- testing approach
- likely failure modes

Do not build the application. Produce an implementation blueprint only.
""",
        expected_output="A developer-ready Markdown implementation blueprint.",
        agent=developer,
        context=[analyze_task, architecture_task],
    )

    review_task = Task(
        description=f"""
Review all prior work against the ORIGINAL intent below.

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


def main() -> None:
    load_dotenv(ROOT / ".env")

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
        )

    intent_text = read_intent()
    crew = build_crew(intent_text)
    result = crew.kickoff()

    report = clean_output(result.raw)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(report, encoding="utf-8")

    print("\nCrew complete.")
    print(f"Final report written to: {OUTPUT_PATH}")

    # Systems verify: deterministic gate, independent of the Reviewer agent.
    errors = verify_report(report)
    if errors:
        print("VERIFICATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print(f"VERIFICATION PASSED (reviewer verdict: {get_verdict(report)})")


if __name__ == "__main__":
    main()
