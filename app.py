import streamlit as st
import plotly.express as px
import pandas as pd
import csv
import io
from agent import run_agent
from database import init_db, save_conversation, get_all_conversations

init_db()

st.set_page_config(page_title="Research Agent", page_icon="🔬", layout="wide")

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

st.title("🔬 Scientific Research Agent")
st.caption("Powered by LangChain · Wikipedia · ArXiv · PubMed · Calculator")

if "history" not in st.session_state:
    st.session_state.history = []
if "chat" not in st.session_state:
    st.session_state.chat = []

def get_tool_icon(tool_name: str) -> str:
    icons = {
        "wikipedia": "📖",
        "arxiv": "📄",
        "pubmed_search": "🧬",
        "calculate": "🧮",
    }
    return icons.get(tool_name.lower(), "🔧")

def export_csv(rows):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp", "Question", "Answer", "Tools Used", "Tokens"])
    for row in rows:
        writer.writerow(row)
    return output.getvalue().encode("utf-8")

# CHAT HISTORY
for item in st.session_state.chat:
    st.markdown(f'<div class="user-bubble">🧑 {item["question"]}</div>', unsafe_allow_html=True)

    with st.expander("🧠 Agent steps"):
        for step in item["steps"]:
            for tool_name, icon in [("wikipedia", "📖"), ("arxiv", "📄"), ("pubmed_search", "🧬"), ("calculate", "🧮")]:
                step = step.replace(f"`{tool_name}`", f"`{icon} {tool_name}`")
            st.markdown(f'<div class="tool-step">{step}</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="agent-bubble">🤖 {item["answer"]}</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

# INPUT
question = st.chat_input("Ask a scientific question...")

if question:
    with st.spinner("Agent is thinking..."):
        answer, steps, tools_used, tokens_used = run_agent(
            question,
            st.session_state.history,
            model=st.session_state.get("model", "gpt-4o-mini")
        )

    st.session_state.history.append(("user", question))
    st.session_state.history.append(("assistant", answer))
    st.session_state.chat.append({
        "question": question,
        "answer": answer,
        "steps": steps,
        "tools_used": tools_used,
        "tokens_used": tokens_used
    })

    save_conversation(question, answer, tools_used, tokens_used)
    st.rerun()

# SIDEBAR
with st.sidebar:
    st.header("⚙️ Settings")
    st.session_state["model"] = st.selectbox(
        "GPT Model",
        ["gpt-4o-mini", "gpt-3.5-turbo", "gpt-4o"],
        index=0
    )

    st.divider()
    st.header("📊 Statistics")
    rows = get_all_conversations()

    if rows:
        st.metric("Total queries", len(rows))
        total_tokens = sum(r[5] for r in rows)
        st.metric("Total tokens used", total_tokens)

        all_tools = []
        for row in rows:
            if row[4] and row[4] != "none":
                all_tools.extend([t.strip() for t in row[4].split(",")])

        if all_tools:
            tool_counts = pd.Series(all_tools).value_counts().reset_index()
            tool_counts.columns = ["Tool", "Count"]
            tool_counts["Icon"] = tool_counts["Tool"].apply(get_tool_icon)
            tool_counts["Label"] = tool_counts["Icon"] + " " + tool_counts["Tool"]

            fig = px.bar(
                tool_counts,
                x="Label",
                y="Count",
                color="Count",
                color_continuous_scale="teal",
                title="Tool usage"
            )
            fig.update_layout(
                plot_bgcolor="#0a0a0f",
                paper_bgcolor="#0a0a0f",
                font_color="#e2e8f0",
                showlegend=False,
                coloraxis_showscale=False,
                margin=dict(t=40, b=0, l=0, r=0)
            )
            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("⬇️ Export History")
        st.download_button(
            label="Export CSV",
            data=export_csv(rows),
            file_name="research_agent_history.csv",
            mime="text/csv"
        )

        st.divider()
        st.subheader("Recent queries")
        for row in rows[:10]:
            with st.expander(f"🕐 {row[1][:16]} — {row[2][:30]}..."):
                st.markdown(f"**Tools:** {row[4]}")
                st.markdown(f"**Tokens:** {row[5]}")
                st.markdown(f"**Answer:** {row[3][:200]}...")
    else:
        st.info("No conversations yet.")