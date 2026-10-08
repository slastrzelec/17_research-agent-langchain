from utils import esc, format_step, rows_to_csv


def test_esc_neutralises_html():
    out = esc('<script>alert(1)</script><img src=x onerror="y">')
    assert "<" not in out and ">" not in out and '"' not in out


def test_format_step_escapes_and_adds_icon():
    out = format_step("🔧 Using tool: `wikipedia` with query: `<b>x</b>`")
    assert "📖 wikipedia" in out and "<b>" not in out


def test_csv_blocks_formula_injection():
    data = rows_to_csv([("2026-01-01", "=HYPERLINK(\"http://evil\")", "+1+1", "none", 3)]).decode()
    assert "'=HYPERLINK" in data and "'+1+1" in data
    assert data.splitlines()[0] == "Timestamp,Question,Answer,Tools Used,Tokens"
