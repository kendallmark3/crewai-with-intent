# CrewAI + Claude Code Starter

A small, complete example of a CrewAI project designed to be opened in Claude Code and extended from an intent file.

Built on [intent-drive-starter](https://github.com/kendallmark3/intent-drive-starter): the `agents/`, `hooks/`, `context/`, `templates/`, `skills/`, and `docs/` folders come from that base. Learn the methodology at [learnteachmaster.org](https://learnteachmaster.org).

## What it demonstrates

This repo creates a four-agent engineering crew:

1. Requirements Analyst
2. Solution Architect
3. Developer
4. Intent Reviewer

The crew receives a single product intent and produces a structured implementation proposal in `output/final_report.md`.

The point is not the demo itself. The point is the pattern:

**Human declares intent → agents reason and collaborate → system produces an inspectable artifact.**

## Project structure

```text
crewai-claude-starter/
├── README.md
├── requirements.txt          # pinned, tested versions
├── .env.example
├── .gitignore                # keeps .env and generated output out of git
├── .claude/CLAUDE.md         # repo rules for Claude Code
├── .github/workflows/ci.yml  # runs pytest on every push/PR
├── intent/
│   ├── project-intent.md
│   └── current-feature.md    # source of truth for the crew
├── src/
│   ├── main.py               # the CrewAI crew (agents reason)
│   └── verify.py             # deterministic gate (systems verify)
├── tests/                    # offline tests, no API key needed
├── output/                   # final_report.md lands here
└── agents/ hooks/ context/ templates/ skills/ docs/   # from intent-drive-starter
```

## Prerequisites

- Python 3.11+
- An Anthropic API key
- Claude Code installed if you want Claude Code to inspect or modify the repo

## Setup

### 1. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure the model

Copy `.env.example` to `.env` and add your Anthropic API key.

```text
ANTHROPIC_API_KEY=your_key_here
MODEL=anthropic/claude-sonnet-5-5
```

CrewAI 1.x calls Anthropic natively (no LiteLLM). To use a different Claude model, change `MODEL` in `.env`.

### 4. Run it

```bash
python -m src.main
```

The final result is written to `output/final_report.md`, then checked automatically by `src/verify.py`. The run exits with code 1 if the report is missing a required section, has an empty section, or lacks a `Verdict: PASS | PARTIAL | FAIL` line.

Re-check an existing report any time:

```bash
python -m src.verify output/final_report.md
```

### 5. Run the tests

```bash
pytest -q
```

The tests run offline. They check the crew's shape (four agents, sequential order, context chaining) and the verifier's pass/fail behavior. CI runs the same command.

## Using this with Claude Code

Open the repository in Claude Code and give it this instruction:

```text
Read README.md and intent/current-feature.md first.
Treat the intent file as the source of truth.
Inspect the existing CrewAI implementation before changing anything.
Make the smallest changes needed to satisfy the intent.
Preserve the Human -> Agent -> System separation.
Run the application and report what changed, what ran, and any unresolved issues.
```

Claude Code can then modify the crew, add tools, replace the example intent, add deterministic validation, or package the workflow for a larger platform such as Amazon Bedrock AgentCore.

## Architecture

```text
                  HUMAN
                    |
                    v
        intent/current-feature.md
                    |
                    v
              CrewAI Crew
        +-----------------------+
        | Requirements Analyst  |
        | Solution Architect    |
        | Developer             |
        | Reviewer              |
        +-----------------------+
                    |
                    v
          output/final_report.md
                    |
                    v
                 SYSTEM
     src/verify.py  (deterministic gate)
     tests/ + CI    (offline checks)
```

## Why this is intentionally simple

CrewAI can support tools, memory, flows, structured outputs, human approvals, callbacks, and more. This starter avoids all of that initially so the orchestration model stays visible. The only system-side logic is a small deterministic verifier.

Once this runs, the natural next additions are:

- MCP or API tools
- repository inspection tools
- deterministic test execution
- structured Pydantic outputs
- human approval gates
- AgentCore runtime deployment
- observability and evidence capture

## Expected behavior

The Requirements Analyst translates the intent into concrete requirements.

The Solution Architect creates an implementation design.

The Developer turns the design into an implementation plan and sample code approach.

The Intent Reviewer checks everything against the original intent and produces the final report.

The agents execute sequentially so the reasoning chain is easy to understand.

## Intent-Driven Engineering interpretation

The intent file owns the desired outcome and boundaries.

CrewAI owns agent reasoning and collaboration.

Deterministic systems own verification. Today that means `src/verify.py` and the test suite; the Reviewer agent's verdict is an input, not the gate.

That produces the pattern:

```text
Human declares -> Agents reason -> Systems verify
```

