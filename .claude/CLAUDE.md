# Repository Rules
Read intent/current-feature.md first. It is the source of truth.
Always write tests. Run `pytest` before reporting done.
Respect architecture: Human declares -> Agents reason -> Systems verify.
- Agent reasoning lives in src/main.py (CrewAI crew, sequential only).
- Deterministic verification lives in src/verify.py. Never weaken a check to make a run pass.
Never commit .env or anything in output/.
