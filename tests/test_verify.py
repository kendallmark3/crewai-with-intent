from src.verify import REQUIRED_SECTIONS, TITLE, get_verdict, main, verify_report


def make_report(verdict="PASS", drop=None, empty=None, order=None):
    sections = order or REQUIRED_SECTIONS
    parts = [TITLE, ""]
    for h in sections:
        if h == drop:
            continue
        parts.append(h)
        if h != empty:
            body = f"**Verdict:** {verdict}" if h == REQUIRED_SECTIONS[-1] else "Content."
            parts.append(body)
        parts.append("")
    return "\n".join(parts)


def test_valid_report_passes():
    assert verify_report(make_report()) == []
    assert get_verdict(make_report("PARTIAL")) == "PARTIAL"


def test_missing_title_fails():
    assert any("title" in e for e in verify_report(make_report().replace(TITLE, "# Other")))


def test_missing_section_fails():
    errors = verify_report(make_report(drop="## 3. API Design"))
    assert any("API Design" in e for e in errors)


def test_empty_section_fails():
    errors = verify_report(make_report(empty="## 5. Testing Strategy"))
    assert any("empty" in e and "Testing" in e for e in errors)


def test_out_of_order_fails():
    swapped = REQUIRED_SECTIONS[:]
    swapped[1], swapped[2] = swapped[2], swapped[1]
    assert "Sections are out of order" in verify_report(make_report(order=swapped))


def test_missing_verdict_fails():
    text = make_report().replace("**Verdict:** PASS", "Looks fine.")
    assert any("Verdict" in e for e in verify_report(text))


def test_cli_exit_codes(tmp_path):
    good = tmp_path / "good.md"
    good.write_text(make_report())
    bad = tmp_path / "bad.md"
    bad.write_text("# nope")
    assert main([str(good)]) == 0
    assert main([str(bad)]) == 1
    assert main([str(tmp_path / "missing.md")]) == 1
