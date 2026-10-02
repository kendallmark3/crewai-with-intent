# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Rules
- Read `intent/current-feature.md` first. It is the source of truth.
- Always write tests. Run `pytest` before reporting done.
- Respect architecture: Human declares -> Agents reason -> Systems verify.
  - Agent reasoning lives in `src/main.py` (CrewAI crew, sequential only).
  - Deterministic verification lives in `src/verify.py`. Never weaken a check to make a run pass.
- Never commit `.env` or anything in `output/`.
- Respect the intent's Boundaries: no external tools/MCP servers, no autonomous looping, no building the actual HTTP service.

## Commands
Run everything from the repo root. `src` is imported as a package, so always use `python -m`.

```bash
pip install -r requirements.txt                 # pinned versions; bump deliberately, then re-run tests
pytest -q                                       # offline, no API key needed (same as CI)
pytest tests/test_verify.py::test_missing_section_fails   # single test
python -m src.main                              # live run: needs ANTHROPIC_API_KEY in .env; writes output/final_report.md
python -m src.verify output/final_report.md     # re-check an existing report (exit 1 on failure)
python -m src.server                            # web UI API on 127.0.0.1:8787 (CREW_PORT); serves web/dist if built
cd web && npm run build                         # strict TS typecheck + build the React UI
```

`MODEL` in `.env` picks the model (default `anthropic/claude-sonnet-5-5`). CrewAI 1.x calls Anthropic natively, with no LiteLLM.

## Architecture
Flow: `intent/current-feature.md` -> `build_crew()` in `src/main.py` -> `crew.kickoff()` -> `clean_output()` (strips a wrapping ```markdown fence) -> `output/final_report.md` -> `verify_report()` gate -> exit 1 if it fails.

- The crew has four agents (Requirements Analyst -> Solution Architect -> Developer -> Intent Reviewer) and runs `Process.sequential` with `allow_delegation=False`. Each task's `context` is the list of all earlier tasks. The intent text is inserted into the first and last task descriptions.
- **Agent prompts follow the simplest-implementation rule.** Every task starts with `SCOPE_RULE`: simplest implementation that satisfies the intent; assumptions visible and reversible; no assumption becomes architecture unless the intent or repository evidence requires it. Requirements are numbered R1..Rn and every component and step must cite one; assumptions are numbered A1..An with what changes if wrong, and anything depending on one cites it; extras go under "Beyond the intent (needs human approval)" without being planned; the Reviewer's scope check also flags assumptions turned into architecture, and it may not PASS an over-built proposal. `WORD_BUDGETS` caps each output to keep runs fast. Do not add menu-style prompts ("include tech choices, failure modes, ...") back: they cause agent-role over-writing.
- The Reviewer's `**Verdict:** PASS|PARTIAL|FAIL` is reported but **does not gate** the run. Only `src/verify.py` gates it: title, all 7 sections present, in order, non-empty, and a verdict line in section 7. It never calls an LLM.
- The `agents/`, `hooks/`, `context/`, `templates/`, `skills/` and `docs/` folders come from the intent-drive-starter base and are mostly stubs. The actual agents are defined in code in `src/main.py`, not in `agents/*.md`.

- `run_crew()` in `src/main.py` is the single path that runs the crew, writes the report and verifies it. Both `main()` and `src/server.py` call it, so the web UI goes through the same gate. The server binds to 127.0.0.1 only and allows one run at a time; pasted intents are never written to `intent/`.

## Coupling to keep in sync
- **Report headings are duplicated.** The section list in the `review_task` prompt in `src/main.py` must match `TITLE`/`REQUIRED_SECTIONS` in `src/verify.py` exactly. Change both, plus `tests/test_verify.py`, together.
- **Default model** is pinned in `DEFAULT_MODEL`, `.env.example`, the README and `tests/test_main.py::test_default_model_is_current`.
- **Intent file shape:** `tests/test_main.py` requires `## Success Criteria` and `## Boundaries` headings, so a replacement intent must keep them.
- **Server port:** `DEFAULT_PORT` in `src/server.py` and `DEFAULT_PORT` in `web/vite.config.ts` must match; both read `CREW_PORT`.
- **Run result shape:** `RunResult` in `src/main.py`, the JSON in `src/server.py`, and the runtime check in `web/src/api.ts` must agree (`report`, `errors`, `verdict`, `passed`).
- **Crew-shape tests** assert the exact roles, their order, the sequential process, and the context chaining. Adding or reordering agents means updating `test_crew_shape`.
- Offline tests that call `build_crew()` set a dummy `ANTHROPIC_API_KEY` via `monkeypatch.setenv`. Keep doing this in new tests. No API call happens until `kickoff()`.
