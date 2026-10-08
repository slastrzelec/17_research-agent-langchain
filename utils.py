"""Small UI helpers (kept free of Streamlit so they are easy to test)."""
import csv
import html
import io

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
