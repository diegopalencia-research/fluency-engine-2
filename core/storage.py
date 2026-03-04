"""
core/storage.py
Username-keyed session storage and error memory persistence.

Files written to:
  sessions/{username}_sessions.json   — list of session dicts
  memory/{username}_memory.json       — cumulative error patterns

Note: On Streamlit Cloud (ephemeral filesystem), data resets on redeploy.
For production persistence, replace with a database backend.
"""

import json
import os
from datetime import datetime
from pathlib import Path

BASE_DIR     = Path(__file__).parent.parent
SESSIONS_DIR = BASE_DIR / "sessions"
MEMORY_DIR   = BASE_DIR / "memory"

SESSIONS_DIR.mkdir(exist_ok=True)
MEMORY_DIR.mkdir(exist_ok=True)

_MEMORY_TEMPLATE = {
    "grammar_errors":      {},   # {pattern_name: frequency_count}
    "missing_connectors":  [],   # [connector_type_key, ...]
    "habitual_fillers":    {},   # {filler_key: frequency_count}
    "wpm_history":         [],   # [float, ...] last 20 sessions
    "wpm_trend":           "stable",   # "improving" | "declining" | "stable"
    "total_sessions":      0,
    "level_history":       [],   # [str, ...]
    "last_updated":        None
}

_CLEAN_AFTER_N = 5   # remove a pattern from memory after N clean sessions


# ── Helpers ───────────────────────────────────────────────────────────────────
def _sessions_path(username: str) -> Path:
    safe = "".join(c for c in username if c.isalnum() or c in "_-")[:40]
    return SESSIONS_DIR / f"{safe}_sessions.json"

def _memory_path(username: str) -> Path:
    safe = "".join(c for c in username if c.isalnum() or c in "_-")[:40]
    return MEMORY_DIR / f"{safe}_memory.json"

def _load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return default

def _save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


# ── Sessions ──────────────────────────────────────────────────────────────────
def save_session(username: str, session_data: dict) -> int:
    """
    Append a session dict to the user's session log.
    Adds session_n and timestamp if not present.
    Returns the session number.
    """
    path     = _sessions_path(username)
    sessions = _load_json(path, [])

    session_n = len(sessions) + 1
    session_data.setdefault("session_n",  session_n)
    session_data.setdefault("timestamp",  datetime.utcnow().isoformat())
    session_data.setdefault("username",   username)

    sessions.append(session_data)
    _save_json(path, sessions)
    return session_n


def load_sessions(username: str) -> list:
    """Return all sessions for username, most-recent first."""
    sessions = _load_json(_sessions_path(username), [])
    return list(reversed(sessions))


def get_session_count(username: str) -> int:
    return len(_load_json(_sessions_path(username), []))


# ── Error memory ──────────────────────────────────────────────────────────────
def get_error_memory(username: str) -> dict:
    """Load error memory. Returns template if no history exists."""
    import copy
    mem = _load_json(_memory_path(username), None)
    if mem is None:
        return copy.deepcopy(_MEMORY_TEMPLATE)
    # Ensure all keys exist (backwards compat)
    for k, v in _MEMORY_TEMPLATE.items():
        mem.setdefault(k, v)
    return mem


def update_error_memory(username: str, corrections: dict, analysis: dict, level: str) -> dict:
    """
    Update error memory from the latest session's corrections and analysis.

    Logic:
    - Grammar patterns in corrections → increment counter
    - Grammar patterns NOT in corrections (but in memory) → don't increment
    - After _CLEAN_AFTER_N consecutive sessions without error → remove from memory
    - Missing connector types → added to missing_connectors list
    - Habitual fillers → increment counter
    - WPM → recalculate trend

    Returns the updated memory dict.
    """
    mem = get_error_memory(username)

    # ── Grammar errors ──────────────────────────────────────────────────────
    found_patterns = corrections.get("grammar_patterns_found", [])
    for pattern in found_patterns:
        if pattern:
            mem["grammar_errors"][pattern] = mem["grammar_errors"].get(pattern, 0) + 1

    # ── Connector memory ─────────────────────────────────────────────────────
    connector_data  = analysis.get("connector_data", {})
    missing_types   = connector_data.get("missing_types", [])
    current_missing = mem.get("missing_connectors", [])
    # Add newly missing types that aren't already tracked
    for t in missing_types:
        if t not in current_missing:
            current_missing.append(t)
    # Remove types that were used this session
    used_types = list(connector_data.get("found", {}).keys())
    current_missing = [t for t in current_missing if t not in used_types]
    mem["missing_connectors"] = current_missing[:8]  # cap at 8

    # ── Filler memory ─────────────────────────────────────────────────────────
    filler_data = analysis.get("filler_data", {})
    by_type     = filler_data.get("by_type", {})
    for filler_key, finfo in by_type.items():
        mem["habitual_fillers"][filler_key] = (
            mem["habitual_fillers"].get(filler_key, 0) + finfo.get("count", 0)
        )

    # ── WPM trend ─────────────────────────────────────────────────────────────
    wpm = analysis.get("wpm", 0)
    if wpm > 0:
        mem["wpm_history"].append(wpm)
        mem["wpm_history"] = mem["wpm_history"][-20:]  # keep last 20
    if len(mem["wpm_history"]) >= 4:
        recent  = mem["wpm_history"][-4:]
        earlier = mem["wpm_history"][-8:-4] if len(mem["wpm_history"]) >= 8 else mem["wpm_history"][:-4]
        if earlier:
            if sum(recent) / len(recent) > sum(earlier) / len(earlier) * 1.05:
                mem["wpm_trend"] = "improving"
            elif sum(recent) / len(recent) < sum(earlier) / len(earlier) * 0.95:
                mem["wpm_trend"] = "declining"
            else:
                mem["wpm_trend"] = "stable"

    # ── Metadata ──────────────────────────────────────────────────────────────
    mem["total_sessions"] += 1
    mem["level_history"].append(level)
    mem["level_history"] = mem["level_history"][-20:]
    mem["last_updated"]  = datetime.utcnow().isoformat()

    _save_json(_memory_path(username), mem)
    return mem


def clear_memory(username: str) -> None:
    """Reset error memory for username."""
    import copy
    _save_json(_memory_path(username), copy.deepcopy(_MEMORY_TEMPLATE))


def export_sessions_csv(username: str) -> str:
    """Export all sessions as CSV string."""
    import csv, io
    sessions = load_sessions(username)
    if not sessions:
        return ""
    # Flatten for CSV
    fieldnames = [
        "session_n", "timestamp", "cefr_level", "scenario_type",
        "duration_s", "wpm", "pause_count", "pause_rate",
        "filler_count", "filler_rate", "fluency_score",
        "types_used_count", "discourse_score", "assessed_level"
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for s in reversed(sessions):  # chronological
        row = {k: s.get(k, "") for k in fieldnames}
        writer.writerow(row)
    return buf.getvalue()
