"""
app.py
FLUENCY ENGINE — Improved Version
NO API KEYS REQUIRED — Works completely offline

Key improvements:
- Pre-built scenario library (coach-editable)
- Rule-based grammar corrections (no AI needed)
- Student accounts with simple username
- Coach dashboard for monitoring progress
- Common mistakes analysis across students

Session flow:
  Step 1  →  Scenario (from library, CEFR-calibrated)
  Step 2  →  Record (microphone or file upload)
  Step 3  →  Analysis (acoustic + linguistic)
  Step 4  →  Corrections (rule-based, Finishing School format)
  Step 5  →  Next (progress + level check + new scenario)
"""

import json
import time
import datetime
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")
import numpy as np

from core.analyze import analyze_audio
from core.score import compute_fluency_score, assess_cefr_level, check_level_progression, detect_connectors
from core.rule_feedback import generate_rule_based_feedback, detect_connectors_local, detect_fillers_local
from core.scenario_manager import get_scenario, get_available_types, get_scenario_types
from core.storage import (
    save_session, load_sessions, get_session_count,
    get_error_memory, update_error_memory,
    clear_memory, export_sessions_csv
)
from core.pdf_report import generate_pdf
from core.coach_dashboard import (
    get_all_students, get_common_mistakes_across_students,
    get_areas_of_opportunity, get_student_detail, get_class_statistics,
    export_class_data
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Fluency Engine",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
LEVEL_COLORS = {"A1": "#6B7280", "A2": "#3B82F6", "B1": "#10B981", "B2": "#F59E0B", "C1": "#8B5CF6", "C2": "#EF4444"}
LEVEL_LABELS = {"A1": "Beginner", "A2": "Elementary", "B1": "Intermediate", "B2": "Upper-Int.", "C1": "Advanced", "C2": "Mastery"}


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE INITIALIZATION
# ══════════════════════════════════════════════════════════════════════════════
def init_state():
    defaults = {
        "step": 1,
        "username": "",
        "user_role": "student",  # "student" or "coach"
        "cefr_level": "B1",
        "manual_level": False,
        "scenario": None,
        "used_scenario_ids": [],
        "audio_bytes": None,
        "analysis": None,
        "score_data": None,
        "cefr_assess": None,
        "corrections": None,
        "session_saved": False,
        "level_event": None,
        "coach_view": "overview",  # For coach dashboard
        "selected_student": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
def render_sidebar():
    with st.sidebar:
        st.markdown(
            "<h2 style='color:#1F3864;margin-bottom:0'>🎙️ FLUENCY ENGINE</h2>"
            "<p style='color:#6B7280;font-size:12px;margin-top:2px'>English Fluency Training Platform</p>",
            unsafe_allow_html=True
        )
        st.divider()

        # ── Role Selection ─────────────────────────────────────────────────
        st.markdown("**👤 Login**")
        
        role = st.radio("I am a:", ["Student", "Coach"], 
                       index=0 if st.session_state.user_role == "student" else 1,
                       horizontal=True)
        st.session_state.user_role = role.lower()
        
        # ── Username ────────────────────────────────────────────────────────
        username = st.text_input(
            "Username",
            value=st.session_state.username,
            placeholder="Enter your username",
            help="Your progress is saved under this name"
        )
        if username != st.session_state.username:
            st.session_state.username = username
            st.rerun()

        if not st.session_state.username:
            st.warning("Enter a username to continue.")
            st.stop()

        n_sessions = get_session_count(st.session_state.username) if st.session_state.username else 0
        st.caption(f"Sessions completed: **{n_sessions}**")

        st.divider()

        # ── CEFR Level (for students) ───────────────────────────────────────
        if st.session_state.user_role == "student":
            st.markdown("**📊 Your Level**")
            level_col, badge_col = st.columns([3, 1])
            with level_col:
                if st.session_state.manual_level:
                    new_level = st.selectbox(
                        "Level",
                        LEVEL_ORDER,
                        index=LEVEL_ORDER.index(st.session_state.cefr_level),
                        label_visibility="collapsed"
                    )
                    if new_level != st.session_state.cefr_level:
                        st.session_state.cefr_level = new_level
                else:
                    st.caption(f"Auto: {LEVEL_LABELS[st.session_state.cefr_level]}")
            with badge_col:
                lvl = st.session_state.cefr_level
                st.markdown(
                    f"<div style='background:{LEVEL_COLORS[lvl]};color:white;"
                    f"border-radius:6px;padding:4px 8px;text-align:center;"
                    f"font-weight:bold;font-size:14px'>{lvl}</div>",
                    unsafe_allow_html=True
                )
            
            manual = st.toggle("Manual level control", value=st.session_state.manual_level)
            st.session_state.manual_level = manual

            st.divider()

            # ── Error Memory Preview ────────────────────────────────────────
            mem = get_error_memory(st.session_state.username)
            if mem.get("total_sessions", 0) > 0:
                st.markdown("**🧠 Your Focus Areas**")
                grammar_errors = mem.get("grammar_errors", {})
                if grammar_errors:
                    top = sorted(grammar_errors.items(), key=lambda x: -x[1])[:3]
                    st.caption("Patterns to practice:")
                    for pat, cnt in top:
                        st.caption(f"  • {pat.replace('_', ' ').title()}")
                
                wpm_trend = mem.get("wpm_trend", "stable")
                trend_emoji = {"improving": "📈", "declining": "📉", "stable": "➡️"}.get(wpm_trend, "➡️")
                st.caption(f"WPM trend: {trend_emoji} {wpm_trend}")

                if st.button("🗑 Reset my progress", use_container_width=True):
                    clear_memory(st.session_state.username)
                    st.success("Progress reset.")
                    st.rerun()

            st.divider()

            # ── Export Data ─────────────────────────────────────────────────
            if n_sessions > 0:
                st.markdown("**📋 My Data**")
                if st.button("📥 Export CSV", use_container_width=True):
                    csv_data = export_sessions_csv(st.session_state.username)
                    st.download_button(
                        "Download CSV",
                        csv_data,
                        file_name=f"{st.session_state.username}_sessions.csv",
                        mime="text/csv",
                        use_container_width=True
                    )


# ══════════════════════════════════════════════════════════════════════════════
# COACH DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def render_coach_dashboard():
    st.markdown("## 👨‍🏫 Coach Dashboard")
    
    # Navigation tabs
    tabs = st.tabs(["📊 Overview", "👥 Students", "⚠️ Common Mistakes", "📈 Statistics"])
    
    # ── Overview Tab ──────────────────────────────────────────────────────
    with tabs[0]:
        st.markdown("### Class Overview")
        
        stats = get_class_statistics()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Students", stats["total_students"])
        with col2:
            st.metric("Total Sessions", stats["total_sessions"])
        with col3:
            st.metric("Avg Score", f"{stats['avg_score']:.0f}" if stats["avg_score"] else "N/A")
        with col4:
            st.metric("Avg WPM", f"{stats['avg_wpm']:.0f}" if stats["avg_wpm"] else "N/A")
        
        # Most active and highest scoring
        if stats["most_active_student"]:
            col1, col2 = st.columns(2)
            with col1:
                st.success(f"🏆 Most Active: **{stats['most_active_student']['username']}** "
                          f"({stats['most_active_student']['sessions']} sessions)")
            with col2:
                st.info(f"⭐ Highest Score: **{stats['highest_scoring_student']['username']}** "
                       f"({stats['highest_scoring_student']['score']:.0f} avg)")
        
        # Areas of opportunity
        st.markdown("### 🎯 Areas of Opportunity")
        opportunities = get_areas_of_opportunity()
        
        if opportunities:
            for opp in opportunities[:5]:
                priority_color = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(opp["priority"], "⚪")
                with st.expander(f"{priority_color} {opp['area']} ({opp['affected_students']} affected)"):
                    st.write(f"**Type:** {opp['type'].title()}")
                    st.write(f"**Suggestion:** {opp['suggestion']}")
        else:
            st.info("No data available yet. Students need to complete sessions.")
        
        # Export button
        st.divider()
        if st.button("📥 Export Class Data (CSV)"):
            csv_data = export_class_data()
            if csv_data:
                st.download_button(
                    "Download CSV",
                    csv_data,
                    file_name="class_data.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No student data to export.")
    
    # ── Students Tab ─────────────────────────────────────────────────────
    with tabs[1]:
        st.markdown("### Student List")
        
        students = get_all_students()
        
        if not students:
            st.info("No students have used the platform yet.")
        else:
            for student in students:
                with st.expander(f"👤 {student['username']} — {student['current_level']} "
                               f"({student['total_sessions']} sessions)"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Avg Score", f"{student['avg_score']:.0f}")
                    with col2:
                        st.metric("Avg WPM", f"{student['avg_wpm']:.0f}")
                    with col3:
                        trend = "📈 Improving" if student['improving'] else "➡️ Stable"
                        st.metric("Trend", trend)
                    
                    if student['top_errors']:
                        st.caption("**Top errors:**")
                        for err in student['top_errors']:
                            st.caption(f"  • {err['label']}: {err['count']} times")
                    
                    if st.button(f"View Details", key=f"detail_{student['username']}"):
                        st.session_state.selected_student = student['username']
                        st.session_state.coach_view = "student_detail"
                        st.rerun()
    
    # ── Common Mistakes Tab ───────────────────────────────────────────────
    with tabs[2]:
        st.markdown("### Common Mistakes Across All Students")
        
        common = get_common_mistakes_across_students()
        
        if common["total_students"] == 0:
            st.info("No data available yet.")
        else:
            st.caption(f"Analysis based on {common['total_students']} students")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🔴 Grammar Errors")
                if common["grammar_errors"]:
                    for err in common["grammar_errors"][:8]:
                        st.markdown(f"**{err['label']}**: {err['count']} occurrences")
                else:
                    st.caption("No grammar errors tracked yet.")
            
            with col2:
                st.markdown("#### 🔗 Missing Connectors")
                if common["missing_connectors"]:
                    for conn in common["missing_connectors"][:6]:
                        st.markdown(f"**{conn['label']}**: {conn['count']} students need practice")
                else:
                    st.caption("No connector data yet.")
            
            st.markdown("#### 🗣️ Common Fillers")
            if common["fillers"]:
                filler_cols = st.columns(min(5, len(common["fillers"])))
                for i, filler in enumerate(common["fillers"][:5]):
                    with filler_cols[i]:
                        st.metric(filler['label'], filler['count'])
            
            st.markdown("#### 📊 Level Distribution")
            if common["level_distribution"]:
                level_data = common["level_distribution"]
                level_cols = st.columns(len(level_data))
                for i, (level, count) in enumerate(sorted(level_data.items())):
                    with level_cols[i]:
                        st.metric(level, count)
    
    # ── Statistics Tab ───────────────────────────────────────────────────
    with tabs[3]:
        st.markdown("### Detailed Statistics")
        
        students = get_all_students()
        
        if len(students) >= 2:
            # Score distribution
            scores = [s["avg_score"] for s in students]
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.hist(scores, bins=10, color="#2E5DA0", edgecolor="white", alpha=0.7)
            ax.set_xlabel("Average Fluency Score")
            ax.set_ylabel("Number of Students")
            ax.set_title("Score Distribution")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            st.pyplot(fig)
            plt.close(fig)
            
            # WPM vs Score scatter
            wpms = [s["avg_wpm"] for s in students]
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.scatter(wpms, scores, c="#10B981", alpha=0.6, s=100)
            ax.set_xlabel("Average WPM")
            ax.set_ylabel("Average Score")
            ax.set_title("WPM vs Score")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            st.pyplot(fig)
            plt.close(fig)
        else:
            st.info("Need at least 2 students for statistics visualization.")


# ══════════════════════════════════════════════════════════════════════════════
# STUDENT VIEWS
# ══════════════════════════════════════════════════════════════════════════════

# ── Step 1: Scenario ─────────────────────────────────────────────────────────
def render_step1():
    st.markdown("## 📋 Step 1 — Your Scenario")

    level = st.session_state.cefr_level
    username = st.session_state.username
    mem = get_error_memory(username) if username else {}

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(
            f"<p style='color:#6B7280;font-size:13px'>"
            f"Level: <b>{level}</b> — {LEVEL_LABELS[level]} &nbsp;|&nbsp; "
            f"Session #{get_session_count(username) + 1}"
            f"</p>",
            unsafe_allow_html=True
        )
    with col2:
        available_types = ["Auto"] + [t for t in get_available_types(level)]
        scenario_type = st.selectbox(
            "Scenario type",
            available_types,
            label_visibility="collapsed"
        )

    # Generate or display scenario
    generate_clicked = st.button(
        "🎲 Get New Scenario",
        type="primary",
        use_container_width=False
    )

    if generate_clicked or st.session_state.scenario is None:
        with st.spinner("Loading scenario..."):
            force = None if scenario_type == "Auto" else scenario_type
            scenario = get_scenario(
                level,
                scenario_type=force,
                error_memory=mem,
                used_ids=st.session_state.used_scenario_ids
            )
        st.session_state.scenario = scenario
        st.session_state.step = 1
        
        # Track used scenario
        if scenario.get("id"):
            st.session_state.used_scenario_ids.append(scenario["id"])
            # Keep only last 20 to allow cycling
            st.session_state.used_scenario_ids = st.session_state.used_scenario_ids[-20:]

    scenario = st.session_state.scenario
    if not scenario:
        st.error("Could not load scenario. Please try again.")
        return

    # Display scenario
    st.markdown("---")
    sc_type = scenario.get("scenario_type_label", "Practice")
    duration = scenario.get("duration_seconds", 60)

    st.markdown(
        f"<div style='background:#EBF0FB;border-left:5px solid #2E5DA0;"
        f"padding:16px 20px;border-radius:4px'>"
        f"<p style='color:#6B7280;font-size:12px;margin:0 0 6px 0'>"
        f"{sc_type.upper()} · ~{duration}s response</p>"
        f"<p style='color:#1F3864;font-size:18px;font-weight:600;margin:0'>"
        f"{scenario.get('prompt', '')}</p>"
        f"</div>",
        unsafe_allow_html=True
    )

    if scenario.get("context"):
        st.caption(f"📌 Context: {scenario['context']}")

    col_a, col_b = st.columns(2)
    with col_a:
        with st.expander("💡 Vocabulary hints"):
            hints = scenario.get("vocabulary_hints", [])
            if hints:
                for h in hints:
                    st.markdown(f"• **{h}**")
    with col_b:
        with st.expander("🚀 Show me how to start"):
            opener = scenario.get("example_opener", "")
            if opener:
                st.markdown(f"*\"{opener}\"*")

    target = scenario.get("target_structure", "")
    if target:
        st.markdown(
            f"<p style='color:#2E5DA0;font-size:13px;margin-top:8px'>"
            f"🎯 Practice focus: <b>{target}</b></p>",
            unsafe_allow_html=True
        )
    
    # Show personalization hint if available
    if scenario.get("personalization_hint"):
        st.info(f"💡 **Focus for you:** {scenario['personalization_hint']}")

    st.markdown("---")
    if st.button("▶️ I'm ready — go to recording", type="primary", use_container_width=False):
        st.session_state.step = 2
        st.rerun()


# ── Step 2: Record ───────────────────────────────────────────────────────────
def render_step2():
    st.markdown("## 🎙️ Step 2 — Record Your Response")

    scenario = st.session_state.scenario
    if scenario:
        duration = scenario.get("duration_seconds", 60)
        st.markdown(
            f"<div style='background:#FFF8E1;border-left:4px solid #F59E0B;"
            f"padding:10px 16px;border-radius:4px;margin-bottom:16px'>"
            f"<b>{scenario.get('prompt', '')}</b>"
            f"<br><span style='color:#6B7280;font-size:12px'>Target: ~{duration} seconds</span>"
            f"</div>",
            unsafe_allow_html=True
        )

    tab1, tab2 = st.tabs(["🎤 Record live", "📂 Upload file"])

    audio_bytes = None

    with tab1:
        st.info("Click **Start Recording**, speak your response, then click **Stop**.")
        try:
            from audio_recorder_streamlit import audio_recorder
            audio_bytes = audio_recorder(
                text="",
                recording_color="#EF4444",
                neutral_color="#1F3864",
                icon_size="2x",
                pause_threshold=2.0,
                sample_rate=16000
            )
            if audio_bytes:
                st.audio(audio_bytes, format="audio/wav")
                st.success(f"Recorded {len(audio_bytes) / 1024:.0f} KB. Ready to analyze.")
        except ImportError:
            st.warning("audio-recorder-streamlit not installed. Use the upload tab.")

    with tab2:
        uploaded = st.file_uploader(
            "Upload audio (WAV, MP3, M4A, OGG, WEBM)",
            type=["wav", "mp3", "m4a", "ogg", "webm"]
        )
        if uploaded:
            audio_bytes = uploaded.read()
            st.audio(audio_bytes)
            st.success(f"File loaded: {uploaded.name} ({len(audio_bytes) / 1024:.0f} KB)")

    if audio_bytes:
        st.session_state.audio_bytes = audio_bytes
        st.markdown("---")
        if st.button("🔬 Analyze my response", type="primary", use_container_width=False):
            st.session_state.step = 3
            st.rerun()

    st.markdown("---")
    if st.button("← Back to scenario"):
        st.session_state.step = 1
        st.rerun()


# ── Step 3: Analysis ─────────────────────────────────────────────────────────
def render_step3():
    st.markdown("## 📊 Step 3 — Analysis")

    if not st.session_state.audio_bytes:
        st.error("No audio found. Please go back and record or upload audio.")
        if st.button("← Back"):
            st.session_state.step = 2
            st.rerun()
        return

    # Run analysis if not already done
    if st.session_state.analysis is None:
        progress = st.progress(0, text="Transcribing audio...")
        time.sleep(0.2)
        with st.spinner("Running acoustic analysis..."):
            analysis = analyze_audio(
                st.session_state.audio_bytes,
                openai_api_key=None  # Use local whisper
            )
        progress.progress(50, text="Computing fluency score...")

        if analysis.get("error"):
            st.error(f"Analysis error: {analysis['error']}")
            return

        # Scoring
        connector_data = detect_connectors(analysis.get("transcript", ""))
        analysis["connector_data"] = connector_data

        score_data = compute_fluency_score(
            wpm=analysis["wpm"],
            pause_rate=analysis["pause_rate"],
            filler_rate=analysis["filler_rate"],
            level=st.session_state.cefr_level,
            transcript=analysis.get("transcript", "")
        )
        score_data["connector_data"] = connector_data

        cefr_assess = assess_cefr_level(
            wpm=analysis["wpm"],
            pause_rate=analysis["pause_rate"],
            filler_rate=analysis["filler_rate"],
            fluency_score=score_data["fluency_score"]
        )

        st.session_state.analysis = analysis
        st.session_state.score_data = score_data
        st.session_state.cefr_assess = cefr_assess
        progress.progress(100, text="Done.")
        time.sleep(0.3)
        progress.empty()

    analysis = st.session_state.analysis
    score_data = st.session_state.score_data
    cefr_assess = st.session_state.cefr_assess

    # ── Score header ──────────────────────────────────────────────────────
    fluency_score = score_data["fluency_score"]
    grade = score_data["grade"]
    grade_colors = {"Excellent": "#10B981", "Good": "#3B82F6", "Developing": "#F59E0B", "Needs Work": "#EF4444"}
    grade_color = grade_colors.get(grade, "#6B7280")

    col1, col2, col3 = st.columns([1, 2, 2])
    with col1:
        st.markdown(
            f"<div style='background:#1F3864;border-radius:12px;padding:20px;"
            f"text-align:center;color:white'>"
            f"<p style='font-size:42px;font-weight:800;margin:0'>{fluency_score:.0f}</p>"
            f"<p style='font-size:12px;margin:0;opacity:0.8'>FLUENCY SCORE</p>"
            f"</div>",
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            f"<div style='padding:10px'>"
            f"<p style='font-size:22px;font-weight:700;color:{grade_color};margin:0'>{grade}</p>"
            f"<p style='color:#6B7280;font-size:13px'>{score_data['interpretation']}</p>"
            f"<p style='color:#2E5DA0;font-size:13px;margin:4px 0 0 0'>"
            f"CEFR assessed: <b>{cefr_assess['assessed_level']}</b>  "
            f"({cefr_assess['confidence'] * 100:.0f}% confidence)</p>"
            f"</div>",
            unsafe_allow_html=True
        )
    with col3:
        components = [
            ("WPM", score_data["wpm_component"], "#3B82F6"),
            ("Pauses", score_data["pause_component"], "#10B981"),
            ("Fillers", score_data["filler_component"], "#F59E0B"),
        ]
        for name, val, col in components:
            st.markdown(f"<p style='margin:2px 0;font-size:12px;color:#6B7280'>{name}</p>", unsafe_allow_html=True)
            st.progress(int(val), text=f"{val:.0f}/100")

    st.divider()

    # ── Metric cards ──────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    metric_style = "border:1px solid #E5E7EB;border-radius:8px;padding:12px;text-align:center"

    with m1:
        st.markdown(f"<div style='{metric_style}'><p style='font-size:22px;font-weight:700;margin:0;color:#1F3864'>{analysis['wpm']:.0f}</p><p style='font-size:11px;color:#6B7280;margin:0'>WPM</p></div>", unsafe_allow_html=True)
    with m2:
        st.markdown(f"<div style='{metric_style}'><p style='font-size:22px;font-weight:700;margin:0;color:#1F3864'>{analysis['pause_count']}</p><p style='font-size:11px;color:#6B7280;margin:0'>Pauses ({analysis['pause_rate']:.1f}/min)</p></div>", unsafe_allow_html=True)
    with m3:
        st.markdown(f"<div style='{metric_style}'><p style='font-size:22px;font-weight:700;margin:0;color:#1F3864'>{analysis['filler_count']}</p><p style='font-size:11px;color:#6B7280;margin:0'>Fillers ({analysis['filler_rate']:.1f}/min)</p></div>", unsafe_allow_html=True)
    with m4:
        conn_data = analysis.get("connector_data", {})
        st.markdown(f"<div style='{metric_style}'><p style='font-size:22px;font-weight:700;margin:0;color:#1F3864'>{conn_data.get('types_used_count', 0)}</p><p style='font-size:11px;color:#6B7280;margin:0'>Connector types</p></div>", unsafe_allow_html=True)
    with m5:
        st.markdown(f"<div style='{metric_style}'><p style='font-size:22px;font-weight:700;margin:0;color:#1F3864'>{analysis['duration_s']:.0f}s</p><p style='font-size:11px;color:#6B7280;margin:0'>Duration</p></div>", unsafe_allow_html=True)

    st.divider()

    # ── Waveform ──────────────────────────────────────────────────────────
    waveform = analysis.get("waveform", [])
    if waveform:
        fig, ax = plt.subplots(figsize=(10, 1.5))
        x = np.linspace(0, analysis["duration_s"], len(waveform))
        ax.fill_between(x, waveform, alpha=0.6, color="#2E5DA0")
        ax.fill_between(x, [-v for v in waveform], alpha=0.6, color="#2E5DA0")
        for pause in analysis.get("pauses", []):
            ax.axvspan(pause["start_s"], pause["end_s"], alpha=0.25, color="#EF4444")
        ax.set_xlim(0, analysis["duration_s"])
        ax.set_ylim(-1.1, 1.1)
        ax.set_xlabel("Time (seconds)", fontsize=8)
        ax.set_yticks([])
        ax.tick_params(axis='x', labelsize=7)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        plt.tight_layout()
        st.pyplot(fig, use_container_width=True)
        st.caption("🔴 Red zones = detected pauses (>0.4s)")
        plt.close(fig)

    # ── Transcript ────────────────────────────────────────────────────────
    transcript = analysis.get("transcript", "")
    with st.expander("📝 Transcript", expanded=True):
        if transcript:
            highlighted = transcript
            filler_meta = json.loads(
                (Path(__file__).parent / "data" / "filler_patterns.json").read_text()
            )["fillers"]
            import re
            for key, meta in filler_meta.items():
                pat = re.compile(meta["pattern"], re.IGNORECASE)
                highlighted = pat.sub(
                    lambda m: f"<mark style='background:#FEF3C7;border-radius:3px'>{m.group()}</mark>",
                    highlighted
                )
            st.markdown(f"<p style='line-height:1.8'>{highlighted}</p>", unsafe_allow_html=True)
        else:
            st.info("No transcript available.")

    # ── Connectors used ───────────────────────────────────────────────────
    conn_data = analysis.get("connector_data", {})
    if conn_data.get("found"):
        with st.expander("🔗 Connectors detected"):
            for ctype, words in conn_data["found"].items():
                st.markdown(f"✅ **{ctype.replace('_', ' ').title()}**: {', '.join(words)}")
        if conn_data.get("missing_types"):
            st.markdown(
                "<p style='color:#F59E0B;font-size:13px'>⚠️ Connector types not used: "
                + ", ".join(conn_data["missing_types"][:4]) + "</p>",
                unsafe_allow_html=True
            )

    st.markdown("---")
    if st.button("▶️ Get corrections", type="primary"):
        st.session_state.step = 4
        st.rerun()

    if st.button("← Back to recording"):
        st.session_state.analysis = None
        st.session_state.score_data = None
        st.session_state.step = 2
        st.rerun()


# ── Step 4: Corrections ──────────────────────────────────────────────────────
def render_step4():
    st.markdown("## ✍️ Step 4 — Finishing School Corrections")

    if st.session_state.corrections is None:
        with st.spinner("Generating personalized corrections..."):
            mem = get_error_memory(st.session_state.username)
            corrections = generate_rule_based_feedback(
                transcript=st.session_state.analysis.get("transcript", ""),
                scenario=st.session_state.scenario,
                analysis=st.session_state.analysis,
                level=st.session_state.cefr_level
            )
        st.session_state.corrections = corrections

    corrections = st.session_state.corrections

    if corrections.get("error"):
        st.error(f"Correction generation failed: {corrections['error']}")
        return

    # ── Task relevance ────────────────────────────────────────────────────
    task_relevance = corrections.get("task_relevance", "")
    if task_relevance:
        st.markdown(
            f"<div style='background:#F0FDF4;border-left:4px solid #10B981;"
            f"padding:10px 16px;border-radius:4px;margin-bottom:12px'>"
            f"<b>Task Relevance:</b> {task_relevance}</div>",
            unsafe_allow_html=True
        )

    # ── Sentence corrections ──────────────────────────────────────────────
    sentence_corrections = corrections.get("sentence_corrections", [])
    st.markdown("### 🔴 Grammar & Phrasing Corrections")

    if not sentence_corrections:
        st.success("✅ No significant grammar errors detected in this session!")
    else:
        for i, corr in enumerate(sentence_corrections):
            orig = corr.get("original", "")
            corrected = corr.get("corrected", "")
            rule = corr.get("rule", "")
            repeat = corr.get("repeat_prompt", f"Please say: {corrected}")

            with st.container():
                st.markdown(
                    f"<div style='background:#FFF5F5;border-left:4px solid #EF4444;"
                    f"padding:12px 16px;border-radius:4px;margin-bottom:8px'>"
                    f"<p style='margin:0 0 4px 0;color:#EF4444;font-size:12px'>ERROR {i + 1}"
                    + (f" · {rule}" if rule else "") +
                    f"</p>"
                    f"<p style='margin:0;font-size:14px'>"
                    f"<span style='color:#EF4444;text-decoration:line-through'>{orig}</span>"
                    f" → <span style='color:#10B981;font-weight:600'>{corrected}</span></p>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                st.markdown(
                    f"<p style='color:#2E5DA0;font-size:13px;margin:-4px 0 8px 16px'>"
                    f"🗣 <i>{repeat}</i></p>",
                    unsafe_allow_html=True
                )

    st.divider()

    # ── Connector feedback ────────────────────────────────────────────────
    conn_fb = corrections.get("connector_feedback", {})
    missing_type = conn_fb.get("strongest_missing", "")
    if missing_type:
        example = conn_fb.get("example_sentence", "")
        st.markdown("### 🔗 Connector Feedback")
        st.markdown(
            f"<div style='background:#EFF6FF;border-left:4px solid #3B82F6;"
            f"padding:12px 16px;border-radius:4px'>"
            f"<b>Missing connector type: {missing_type.replace('_', ' ').title()}</b><br>"
            f"Try: <i>\"{example}\"</i></div>",
            unsafe_allow_html=True
        )
        st.markdown("")

    # ── Filler feedback ───────────────────────────────────────────────────
    filler_fb = corrections.get("filler_feedback", {})
    worst_filler = filler_fb.get("worst_offender", "")
    if worst_filler:
        tip = filler_fb.get("replacement_tip", "")
        st.markdown("### 🗣️ Filler Reduction")
        st.markdown(
            f"<div style='background:#FFFBEB;border-left:4px solid #F59E0B;"
            f"padding:12px 16px;border-radius:4px'>"
            f"<b>Most frequent filler: \"{worst_filler}\"</b><br>"
            f"Tip: {tip}</div>",
            unsafe_allow_html=True
        )
        st.markdown("")

    # ── Narrative coaching ────────────────────────────────────────────────
    narrative = corrections.get("narrative_coaching", "")
    if narrative:
        st.markdown("### 💬 Coaching Summary")
        st.markdown(
            f"<div style='background:#F0F4FF;border-radius:8px;padding:16px 20px;"
            f"font-size:14px;line-height:1.8;color:#1F3864'>{narrative}</div>",
            unsafe_allow_html=True
        )

    st.divider()

    # ── Save session ──────────────────────────────────────────────────────
    if not st.session_state.session_saved:
        analysis = st.session_state.analysis
        score_data = st.session_state.score_data
        cefr_assess = st.session_state.cefr_assess
        conn_data = analysis.get("connector_data", {})

        session_data = {
            "cefr_level": st.session_state.cefr_level,
            "scenario_type": st.session_state.scenario.get("scenario_type", ""),
            "duration_s": analysis.get("duration_s", 0),
            "wpm": analysis.get("wpm", 0),
            "pause_count": analysis.get("pause_count", 0),
            "pause_rate": analysis.get("pause_rate", 0),
            "filler_count": analysis.get("filler_count", 0),
            "filler_rate": analysis.get("filler_rate", 0),
            "fluency_score": score_data.get("fluency_score", 0),
            "wpm_component": score_data.get("wpm_component", 0),
            "pause_component": score_data.get("pause_component", 0),
            "filler_component": score_data.get("filler_component", 0),
            "types_used_count": conn_data.get("types_used_count", 0),
            "discourse_score": conn_data.get("discourse_score", 0),
            "assessed_level": cefr_assess.get("assessed_level", ""),
            "grammar_patterns": corrections.get("grammar_patterns_found", []),
        }
        save_session(st.session_state.username, session_data)

        # Update error memory
        mem = update_error_memory(
            st.session_state.username,
            corrections,
            analysis,
            st.session_state.cefr_level
        )

        # Check level progression
        all_sessions = load_sessions(st.session_state.username)
        prog = check_level_progression(all_sessions, st.session_state.cefr_level)
        if prog["action"] in ("advance", "drop"):
            st.session_state.level_event = prog
            if not st.session_state.manual_level:
                st.session_state.cefr_level = prog["new_level"]

        st.session_state.session_saved = True

    if st.button("▶️ Continue to progress", type="primary"):
        st.session_state.step = 5
        st.rerun()


# ── Step 5: Next / Progress ──────────────────────────────────────────────────
def render_step5():
    st.markdown("## 🎯 Step 5 — Progress & Next Session")

    # ── Level event announcement ──────────────────────────────────────────
    event = st.session_state.level_event
    if event and event.get("action") != "maintain":
        action = event["action"]
        new_lv = event["new_level"]
        if action == "advance":
            st.balloons()
            st.success(
                f"🎉 **Level Up!** You've advanced to **{new_lv} — {LEVEL_LABELS[new_lv]}**!  \n"
                f"{event['reason']}"
            )
        elif action == "drop":
            st.warning(
                f"📉 Level adjusted to **{new_lv} — {LEVEL_LABELS[new_lv]}** for more targeted practice.  \n"
                f"{event['reason']}"
            )
        st.session_state.level_event = None

    # ── Score summary ─────────────────────────────────────────────────────
    score_data = st.session_state.score_data
    if score_data:
        score = score_data["fluency_score"]
        grade = score_data["grade"]
        corrections = st.session_state.corrections or {}
        patterns = corrections.get("grammar_patterns_found", [])
        next_focus = patterns[0] if patterns else (
            (corrections.get("connector_feedback") or {}).get("strongest_missing", "Continue practising")
        )
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Session Score", f"{score:.0f}/100", delta=None)
            st.caption(f"Grade: {grade}")
        with col2:
            st.markdown(
                f"<div style='background:#EBF0FB;border-radius:8px;padding:12px'>"
                f"<p style='font-size:12px;color:#6B7280;margin:0'>NEXT SESSION FOCUS</p>"
                f"<p style='font-size:16px;font-weight:700;color:#1F3864;margin:0'>"
                f"{next_focus.replace('_', ' ').title() if next_focus else '—'}</p>"
                f"</div>",
                unsafe_allow_html=True
            )

    st.divider()

    # ── Progress chart ────────────────────────────────────────────────────
    sessions = load_sessions(st.session_state.username)
    if len(sessions) >= 2:
        recent = list(reversed(sessions))[-10:]  # last 10 chronological
        scores = [s.get("fluency_score", 0) for s in recent]
        labels = [f"#{s.get('session_n', i + 1)}" for i, s in enumerate(recent)]

        fig, ax = plt.subplots(figsize=(8, 2.5))
        ax.plot(labels, scores, "o-", color="#2E5DA0", linewidth=2, markersize=6)
        ax.fill_between(range(len(scores)), scores, alpha=0.15, color="#2E5DA0")
        ax.set_ylim(0, 100)
        ax.set_ylabel("Fluency Score", fontsize=9)
        ax.tick_params(labelsize=8)
        ax.grid(axis="y", alpha=0.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout()
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
    else:
        st.info("Complete more sessions to see your progress chart!")

    # ── PDF report ────────────────────────────────────────────────────────
    st.divider()
    st.markdown("**📄 Session Report**")

    all_sessions = load_sessions(st.session_state.username)
    session_n = len(all_sessions)

    if st.button("Generate PDF Report", use_container_width=False):
        with st.spinner("Generating PDF..."):
            try:
                pdf_bytes = generate_pdf(
                    username=st.session_state.username,
                    session_n=session_n,
                    level=st.session_state.cefr_level,
                    scenario=st.session_state.scenario or {},
                    analysis=st.session_state.analysis or {},
                    score_data=st.session_state.score_data or {},
                    corrections=st.session_state.corrections or {},
                    cefr_assessment=st.session_state.cefr_assess or {},
                )
                st.download_button(
                    "📥 Download PDF",
                    data=pdf_bytes,
                    file_name=f"{st.session_state.username}_session_{session_n}.pdf",
                    mime="application/pdf",
                    use_container_width=False
                )
            except Exception as e:
                st.error(f"PDF generation failed: {e}")

    st.divider()

    # ── Start next session ────────────────────────────────────────────────
    st.markdown("**Ready for the next scenario?**")
    if st.button("🎲 Start Next Session", type="primary", use_container_width=False):
        # Reset for new session
        st.session_state.step = 1
        st.session_state.scenario = None
        st.session_state.audio_bytes = None
        st.session_state.analysis = None
        st.session_state.score_data = None
        st.session_state.cefr_assess = None
        st.session_state.corrections = None
        st.session_state.session_saved = False
        st.rerun()


# ── Step Progress Bar ─────────────────────────────────────────────────────────
def render_step_bar(current_step: int):
    steps = ["Scenario", "Record", "Analysis", "Corrections", "Progress"]
    cols = st.columns(len(steps))
    for i, (col, label) in enumerate(zip(cols, steps)):
        step_n = i + 1
        if step_n < current_step:
            bg, fg, border = "#1F3864", "white", "#1F3864"
            icon = "✓"
        elif step_n == current_step:
            bg, fg, border = "#2E5DA0", "white", "#2E5DA0"
            icon = str(step_n)
        else:
            bg, fg, border = "white", "#9CA3AF", "#E5E7EB"
            icon = str(step_n)
        with col:
            st.markdown(
                f"<div style='text-align:center;padding:6px 4px;"
                f"background:{bg};border:1px solid {border};border-radius:6px'>"
                f"<span style='color:{fg};font-size:11px;font-weight:600'>{icon} {label}</span>"
                f"</div>",
                unsafe_allow_html=True
            )
    st.markdown("<div style='margin-bottom:16px'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    render_sidebar()

    # Header
    st.markdown(
        "<h1 style='color:#1F3864;margin-bottom:4px'>FLUENCY ENGINE</h1>"
        "<p style='color:#6B7280;font-size:13px;margin-top:0'>"
        "Adaptive spoken English training · CEFR A1–C2 · No API keys needed</p>",
        unsafe_allow_html=True
    )

    # Route based on role
    if st.session_state.user_role == "coach":
        render_coach_dashboard()
    else:
        # Student flow
        render_step_bar(st.session_state.step)
        step = st.session_state.step

        if step == 1:
            render_step1()
        elif step == 2:
            render_step2()
        elif step == 3:
            render_step3()
        elif step == 4:
            render_step4()
        elif step == 5:
            render_step5()


if __name__ == "__main__":
    main()
