"""Deterministic verification of the crew's final report.

Agents reason; systems verify. This module never calls an LLM.
Usage: python -m src.verify output/final_report.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

TITLE = "# Final Engineering Recommendation"
REQUIRED_SECTIONS = [
    "## 1. Interpreted Requirements",
    "## 2. Architecture",
    "## 3. API Design",
    "## 4. Implementation Approach",
    "## 5. Testing Strategy",
    "## 6. Risks and Assumptions",
    "## 7. Intent Compliance Review",
]
VERDICT_PATTERN = re.compile(r"verdict\W*\s*(PASS|PARTIAL|FAIL)\b", re.IGNORECASE)


def _section_bodies(text: str) -> dict[str, str]:
    """Map each required heading to the text under it (up to the next ## heading)."""
    lines = text.splitlines()
    bodies: dict[str, list[str]] = {}
    current = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            current = stripped if stripped in REQUIRED_SECTIONS else None
            if current:
                bodies[current] = []
            continue
        if current is not None:
            bodies[current].append(line)
    return {k: "\n".join(v).strip() for k, v in bodies.items()}


def verify_report(text: str) -> list[str]:
    """Return a list of problems. Empty list means the report passes."""
    errors: list[str] = []
    lines = [l.strip() for l in text.splitlines()]

    if TITLE not in lines:
        errors.append(f"Missing title: {TITLE!r}")

    positions = []
    for heading in REQUIRED_SECTIONS:
        if heading in lines:
            positions.append(lines.index(heading))
        else:
            errors.append(f"Missing section: {heading!r}")
    if len(positions) == len(REQUIRED_SECTIONS) and positions != sorted(positions):
        errors.append("Sections are out of order")

    bodies = _section_bodies(text)
    for heading in REQUIRED_SECTIONS:
        if heading in bodies and not bodies[heading]:
            errors.append(f"Section is empty: {heading!r}")

    compliance = bodies.get(REQUIRED_SECTIONS[-1], "")
    if compliance and not VERDICT_PATTERN.search(compliance):
        errors.append("Intent Compliance Review has no 'Verdict: PASS|PARTIAL|FAIL' line")

    return errors


def get_verdict(text: str) -> str | None:
    compliance = _section_bodies(text).get(REQUIRED_SECTIONS[-1], "")
    match = VERDICT_PATTERN.search(compliance)
    return match.group(1).upper() if match else None


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    path = Path(argv[0]) if argv else Path("output/final_report.md")
    if not path.exists():
        print(f"FAIL: report not found: {path}")
        return 1
    text = path.read_text(encoding="utf-8")
    errors = verify_report(text)
    if errors:
        print(f"FAIL: {path}")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"PASS: {path} (reviewer verdict: {get_verdict(text)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
