import uuid

import pandas as pd
import plotly.express as px
import streamlit as st

from agent import run_agent
from database import get_conversations, init_db, save_conversation
from limits import (ALLOWED_MODELS, MAX_QUESTIONS_PER_SESSION, LimitExceeded,
                    SessionUsage, UsageLimiter)
from utils import esc, format_step, rows_to_csv, tool_icon

init_db()

st.set_page_config(page_title="Research Agent", page_icon="🔬", layout="wide")

# Static CSS only: no dynamic value is ever interpolated into this block.
st.markdown("""
<style>
.user-bubble {
    background: #2d2d3d;
    border-radius: 18px 18px 4px 18px;
    padding: 12px 18px;
    margin: 8px 0;
    max-width: 80%;
    margin-left: auto;
    color: #e2e8f0;
}
.agent-bubble {
    background: #1a1a2e;
    border-radius: 18px 18px 18px 4px;
    padding: 12px 18px;
    margin: 8px 0;
    max-width: 80%;
    border-left: 3px solid #00ff9d;
    color: #e2e8f0;
}
.tool-step {
    font-size: 0.85rem;
    padding: 4px 0;
    color: #94a3b8;
}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_limiter() -> UsageLimiter:
    """One daily budget shared by all visitors of this process."""
    return UsageLimiter()


limiter = get_limiter()

if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex
if "usage" not in st.session_state:
    st.session_state.usage = SessionUsage()
if "history" not in st.session_state:
    st.session_state.history = []
if "chat" not in st.session_state:
    st.session_state.chat = []

session_id = st.session_state.session_id

# SIDEBAR (settings first, so the selected model applies to the question below)
with st.sidebar:
    st.header("⚙️ Settings")
    model = st.selectbox("GPT Model", ALLOWED_MODELS, index=0,
                         help="gpt-4o uses 15× more of your session budget than gpt-4o-mini.")
    st.caption(
        f"Demo limits: {MAX_QUESTIONS_PER_SESSION} questions per session. "
        "Your questions are sent to OpenAI and stored for 30 days (visible only to this session). "
        "Please do not enter personal data."
    )

st.title("🔬 Scientific Research Agent")
st.caption("Powered by LangChain · Wikipedia · ArXiv · PubMed · Calculator")

# CHAT HISTORY (every dynamic value is HTML-escaped)
for item in st.session_state.chat:
    st.markdown(f'<div class="user-bubble">🧑 {esc(item["question"])}</div>', unsafe_allow_html=True)

    with st.expander("🧠 Agent steps"):
        for step in item["steps"]:
            st.markdown(f'<div class="tool-step">{format_step(step)}</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="agent-bubble">🤖 {esc(item["answer"])}</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

# INPUT
question = st.chat_input("Ask a scientific question...")

if question:
    try:
        st.session_state.usage.check(question, model)
        limiter.check()
        with st.spinner("Agent is thinking..."):
            answer, steps, tools_used, tokens_used = run_agent(
                question, st.session_state.history, model=model
            )
    except LimitExceeded as e:
        st.warning(str(e))
    except Exception as e:  # network / OpenAI / recursion-limit errors
        st.error(f"The agent could not answer ({type(e).__name__}). Please try again.")
    else:
        weighted = st.session_state.usage.record(model, tokens_used)
        limiter.add(weighted)
        st.session_state.history.append(("user", question))
        st.session_state.history.append(("assistant", answer))
        st.session_state.chat.append({
            "question": question, "answer": answer, "steps": steps,
            "tools_used": tools_used, "tokens_used": tokens_used,
        })
        save_conversation(session_id, question, answer, tools_used, tokens_used)
        st.rerun()

# SIDEBAR: statistics of THIS session only
with st.sidebar:
    st.divider()
    st.header("📊 Your session")
    rows = get_conversations(session_id)  # (timestamp, question, answer, tools_used, tokens_used)

    if rows:
        st.metric("Queries", len(rows))
        st.metric("Tokens used", sum(r[4] or 0 for r in rows))

        all_tools = []
        for r in rows:
            if r[3] and r[3] != "none":
                all_tools.extend(t.strip() for t in r[3].split(","))

        if all_tools:
            tool_counts = pd.Series(all_tools).value_counts().reset_index()
            tool_counts.columns = ["Tool", "Count"]
            tool_counts["Label"] = tool_counts["Tool"].apply(tool_icon) + " " + tool_counts["Tool"]

            fig = px.bar(tool_counts, x="Label", y="Count", color="Count",
                         color_continuous_scale="teal", title="Tool usage")
            fig.update_layout(
                plot_bgcolor="#0a0a0f", paper_bgcolor="#0a0a0f", font_color="#e2e8f0",
                showlegend=False, coloraxis_showscale=False,
                margin=dict(t=40, b=0, l=0, r=0),
            )
            st.plotly_chart(fig)

        st.divider()
        st.subheader("⬇️ Export your history")
        st.download_button("Export CSV", data=rows_to_csv(rows),
                           file_name="research_agent_history.csv", mime="text/csv")

        st.divider()
        st.subheader("Recent queries")
        for r in rows[:10]:
            with st.expander(f"🕐 {r[0][:16]} — {r[1][:30]}..."):
                st.text(f"Tools: {r[3]}\nTokens: {r[4]}\nAnswer: {r[2][:200]}...")
    else:
        st.info("No conversations yet.")
