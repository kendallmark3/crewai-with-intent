# Architecture
- `intent/current-feature.md`: human-authored intent (input).
- `src/main.py`: builds a sequential CrewAI crew (Requirements Analyst -> Solution Architect -> Developer -> Intent Reviewer). Each task receives prior tasks as context.
- `output/final_report.md`: the generated artifact.
- `src/verify.py`: deterministic gate. Checks the report's required sections and compliance review. Exit code 1 on failure.
- `tests/`: offline tests (no API key needed). CI runs these.
