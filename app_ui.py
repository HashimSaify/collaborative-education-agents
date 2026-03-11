"""
app_ui.py
----------
Streamlit web interface for the Collaborative Education Agents system.

Provides an interactive UI where students can:
  - Enter a study topic
  - Select an output type
  - Watch the agents work (progress indicators)
  - View the final educational content rendered as Markdown
  - Inspect the research handoff JSON
  - Download the output as a Markdown file

Usage:
    streamlit run app_ui.py
"""

import json
import time
from datetime import datetime, timezone

import streamlit as st

import config
from config import OUTPUT_TYPES, DEFAULT_OUTPUT_TYPE
from core.orchestrator import EducationOrchestrator
from core.state_manager import PipelineStage
from utils.logger import setup_logger

# Initialise logging
setup_logger()

# ── Page Configuration ────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Collaborative Education Agents",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "Multi-Agent AI Study Material Generator | Powered by CrewAI + OpenAI",
    },
)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* Main background */
    .stApp { background-color: #0e1117; }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1f2e 0%, #0e1117 100%);
    }

    /* Cards */
    .info-card {
        background: #1a1f2e;
        border: 1px solid #2d3548;
        border-radius: 12px;
        padding: 1.2rem;
        margin: 0.5rem 0;
    }

    /* Agent badge */
    .agent-badge {
        display: inline-block;
        background: #1e3a5f;
        color: #60a5fa;
        border: 1px solid #2563eb;
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.8rem;
        font-weight: 600;
        margin: 4px 4px 4px 0;
    }

    /* Status badge */
    .status-success { color: #4ade80; }
    .status-error   { color: #f87171; }
    .status-running { color: #fbbf24; }

    /* Output type description */
    .output-desc {
        font-size: 0.82rem;
        color: #8892a4;
        margin-top: -0.5rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar() -> tuple[str, str]:
    """Renders the sidebar and returns (topic, output_type)."""
    with st.sidebar:
        st.markdown("## 🎓 Education Agents")
        st.markdown("---")

        # Topic input
        st.markdown("### 📚 Study Topic")
        topic = st.text_input(
            "Enter topic",
            placeholder="e.g. Machine Learning Basics",
            label_visibility="collapsed",
        )

        # Output type selector
        st.markdown("### 📄 Output Format")
        output_type_labels = {
            "study_guide":    "📖 Study Guide (Full)",
            "summary":        "📝 Summary (Short)",
            "revision_sheet": "📋 Revision Sheet",
            "bullet_notes":   "• Bullet Notes (Quick)",
        }
        output_type = st.selectbox(
            "Select output type",
            options=OUTPUT_TYPES,
            format_func=lambda x: output_type_labels[x],
            index=OUTPUT_TYPES.index(DEFAULT_OUTPUT_TYPE),
            label_visibility="collapsed",
        )

        # Descriptions
        descriptions = {
            "study_guide":    "Comprehensive multi-section guide with explanations, resources, and revision questions.",
            "summary":        "Quick 2–3 paragraph overview of the topic.",
            "revision_sheet": "Condensed bullet points for last-minute exam revision.",
            "bullet_notes":   "Fast key-concept bullets for quick reference.",
        }
        st.markdown(
            f'<div class="output-desc">{descriptions[output_type]}</div>',
            unsafe_allow_html=True,
        )

        # Generate button
        st.markdown("---")
        run_clicked = st.button(
            "🚀 Generate Study Material",
            use_container_width=True,
            type="primary",
        )

        # System info
        st.markdown("---")
        st.markdown("### ⚙ System")
        st.markdown(
            f'<div class="info-card">'
            f'<b>Model:</b> {config.OPENAI_MODEL}<br>'
            f'<b>Framework:</b> CrewAI<br>'
            f'<b>Agents:</b> Researcher + Writer<br>'
            f'<b>API:</b> {"✔ Configured" if config.OPENAI_API_KEY else "✘ Missing Key"}'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Agent legend
        st.markdown("### 🤖 Active Agents")
        for badge in ["Researcher Agent", "Writer Agent", "Orchestrator"]:
            st.markdown(f'<span class="agent-badge">{badge}</span>', unsafe_allow_html=True)

    return topic, output_type, run_clicked


# ── Main Area ─────────────────────────────────────────────────────────────────

def render_header() -> None:
    """Renders the main page header."""
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("🎓 Collaborative Education Agents")
        st.markdown(
            "**AI-powered study material generator** — "
            "Enter any topic to get a complete, structured study resource."
        )
    with col2:
        st.markdown("""
        <div class="info-card" style="text-align:center;">
            <div style="font-size:2rem;">🤖→📝</div>
            <div style="font-size:0.75rem; color:#8892a4;">
                Researcher → Writer<br>Multi-Agent Pipeline
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_welcome() -> None:
    """Render welcome screen when no session is active."""
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    examples = [
        ("🖥️", "Machine Learning Basics", "study_guide"),
        ("🌿", "Photosynthesis", "revision_sheet"),
        ("🗄️", "DBMS Normalization", "bullet_notes"),
    ]

    for col, (icon, topic, otype) in zip([col1, col2, col3], examples):
        with col:
            st.markdown(
                f'<div class="info-card">'
                f'<div style="font-size:2rem;">{icon}</div>'
                f'<b>{topic}</b><br>'
                f'<span style="color:#60a5fa; font-size:0.8rem;">{otype.replace("_"," ").title()}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("""
    ---
    ### How it works

    1. **Researcher Agent** analyses your topic, extracts key concepts, identifies resources,
       and produces a structured research handoff object.

    2. **Writer Agent** reads the research handoff and transforms it into polished,
       student-friendly educational content.

    3. **You** get a complete, formatted study resource — ready to read, save, or share.

    > This project demonstrates **multi-agent collaboration**, **specialisation**,
    > **structured hand-off protocols**, and **state management** using **CrewAI**.
    """)


def run_pipeline(topic: str, output_type: str) -> None:
    """
    Execute the full agent pipeline and display results.
    Stores session data in st.session_state for display persistence.
    """
    # ── Config validation ─────────────────────────────────────────────────────
    config_errors = config.validate_config()
    if config_errors:
        for err in config_errors:
            st.error(f"⚠ Configuration Error: {err}")
        st.info("Copy `.env.example` → `.env` and add your `OPENAI_API_KEY`.")
        return

    # ── Progress display ──────────────────────────────────────────────────────
    progress_container = st.empty()
    status_container   = st.empty()

    with progress_container.container():
        progress_bar = st.progress(0, text="Initialising pipeline...")

    status_container.info("🔬 **Researcher Agent** is gathering information...")

    # ── Run pipeline ──────────────────────────────────────────────────────────
    try:
        start_time = time.time()

        # Update progress to show researcher running
        progress_bar.progress(20, text="Researcher Agent: Gathering information...")

        orchestrator = EducationOrchestrator()

        # The pipeline is synchronous; Streamlit will block here
        progress_bar.progress(30, text="Researcher Agent: Analysing topic...")
        state_mgr = orchestrator.run(
            topic=topic,
            output_type=output_type,
            verbose=False,  # No Rich console output in Streamlit
        )

        progress_bar.progress(80, text="Writer Agent: Generating content...")
        time.sleep(0.5)  # Brief pause for UX
        progress_bar.progress(100, text="Complete!")

        duration = round(time.time() - start_time, 1)
        state = state_mgr.state

        # ── Store in session state ────────────────────────────────────────────
        st.session_state["last_result"] = {
            "topic":          topic,
            "output_type":    output_type,
            "final_content":  state.final_content,
            "handoff":        state.handoff.model_dump(mode="json") if state.handoff else None,
            "session_id":     state.session_id,
            "duration":       duration,
            "pipeline_stage": state.stage.value,
            "handoff_valid":  state.handoff.validation.is_complete if state.handoff else False,
        }

        status_container.success(
            f"✔ Generated **{output_type.replace('_', ' ').title()}** "
            f"for '{topic}' in **{duration}s**"
        )
        progress_container.empty()

    except Exception as exc:
        progress_container.empty()
        status_container.error(f"❌ Pipeline failed: {exc}")
        st.session_state.pop("last_result", None)


def display_results(result: dict) -> None:
    """Display the stored pipeline results."""
    topic = result["topic"]
    output_type = result["output_type"]
    final_content = result["final_content"]
    handoff = result.get("handoff")
    session_id = result["session_id"]
    duration = result["duration"]

    st.markdown("---")

    # ── Metrics row ───────────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("⏱ Duration",       f"{duration}s")
    m2.metric("📏 Content Length", f"{len(final_content):,} chars")
    m3.metric("🔑 Key Concepts",   str(len(handoff.get("key_concepts", []))) if handoff else "N/A")
    m4.metric("📚 Resources",      str(len(handoff.get("resources", []))) if handoff else "N/A")

    # ── Tabbed output ─────────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["📖 Study Content", "🔬 Research Handoff", "ℹ Session Info"])

    with tab1:
        # Header and download button
        col1, col2 = st.columns([4, 1])
        with col1:
            st.subheader(f"📚 {output_type.replace('_', ' ').title()} — {topic}")
        with col2:
            st.download_button(
                label="⬇ Download .md",
                data=final_content.encode("utf-8"),
                file_name=f"{output_type}_{topic.replace(' ', '_').lower()}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        # Render the content
        st.markdown(final_content)

    with tab2:
        if handoff:
            st.subheader("🔬 Research Handoff (JSON)")
            st.markdown(
                "*This is the structured data produced by the Researcher Agent "
                "and consumed by the Writer Agent — the inter-agent contract.*"
            )

            # Key info
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Key Concepts:**")
                for concept in handoff.get("key_concepts", []):
                    st.markdown(f"- {concept}")
            with col2:
                st.markdown("**Resources:**")
                for r in handoff.get("resources", []):
                    url = r.get("url") or "#"
                    st.markdown(f"- [{r.get('title', 'Resource')}]({url}) ({r.get('type', '')})")

            # Full JSON
            with st.expander("📋 Full Handoff JSON"):
                st.json(handoff)
        else:
            st.info("No handoff data available.")

    with tab3:
        st.subheader("ℹ Pipeline Session Info")
        info = {
            "Session ID":     session_id,
            "Topic":          topic,
            "Output Type":    output_type,
            "Stage":          result["pipeline_stage"],
            "Duration":       f"{duration} seconds",
            "Handoff Valid":  str(result["handoff_valid"]),
        }
        for key, value in info.items():
            col1, col2 = st.columns([1, 2])
            col1.markdown(f"**{key}**")
            col2.markdown(value)


# ── App Entry Point ───────────────────────────────────────────────────────────

def main() -> None:
    """Main Streamlit app."""
    render_header()
    topic, output_type, run_clicked = render_sidebar()

    # ── Handle run ────────────────────────────────────────────────────────────
    if run_clicked:
        if not topic.strip():
            st.warning("⚠ Please enter a study topic in the sidebar.")
        else:
            run_pipeline(topic.strip(), output_type)

    # ── Display results if available ─────────────────────────────────────────
    if "last_result" in st.session_state:
        display_results(st.session_state["last_result"])
    else:
        render_welcome()


if __name__ == "__main__":
    main()
