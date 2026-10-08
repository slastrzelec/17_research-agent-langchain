"""Small UI helpers (kept free of Streamlit so they are easy to test)."""
import csv
import html
import io
import re

TOOL_ICONS = {"wikipedia": "📖", "arxiv": "📄", "pubmed_search": "🧬", "calculate": "🧮"}


def esc(value) -> str:
    """HTML-escape any dynamic value before it is placed inside markup."""
    return html.escape(str(value), quote=True)


def tool_icon(name: str) -> str:
    return TOOL_ICONS.get(name.lower(), "🔧")


def format_step(step: str) -> str:
    """Escape a step line and decorate known tool names with icons."""
    out = esc(step)
    for name, icon in TOOL_ICONS.items():
        out = out.replace(f"`{name}`", f"`{icon} {name}`")
    return out


def _csv_safe(cell):
    if isinstance(cell, str) and cell[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + cell
    return cell


def rows_to_csv(rows) -> bytes:
    """rows: (timestamp, question, answer, tools_used, tokens_used). Formula-safe CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Timestamp", "Question", "Answer", "Tools Used", "Tokens"])
    for row in rows:
        writer.writerow([_csv_safe(c) for c in row])
    return buf.getvalue().encode("utf-8")


_IMG_INLINE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_IMG_REF = re.compile(r"!\[([^\]]*)\]\[[^\]]*\]")
_LATEX_BLOCK = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
_LATEX_INLINE = re.compile(r"\\\((.+?)\\\)", re.DOTALL)


def render_answer(text: str) -> str:
    """Make model output safe and nice for st.markdown (no unsafe_allow_html).

    - images are removed (auto-loaded URLs could leak conversation text to a third party);
    - literal dollar signs are escaped so they are not read as math;
    - LaTeX \\( \\) and \\[ \\] delimiters become $ and $$, which Streamlit renders.
    """
    text = _IMG_INLINE.sub(lambda m: m.group(1), text)
    text = _IMG_REF.sub(lambda m: m.group(1), text)
    text = text.replace("$", "\\$")
    text = _LATEX_BLOCK.sub(lambda m: "$$" + m.group(1).strip() + "$$", text)
    return _LATEX_INLINE.sub(lambda m: "$" + m.group(1).strip() + "$", text)
