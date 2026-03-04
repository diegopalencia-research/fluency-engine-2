"""
core/score.py
Fluency scoring, connector detection, and CEFR level assessment.

Composite Fluency Score formula:
  40% WPM component  + 30% pause component + 30% filler component
  Each component normalized 0–100 relative to CEFR level thresholds.

Connector detection uses full-phrase matching against connector_taxonomy.json.
CEFR assessment cross-references all three acoustic metrics against thresholds.
"""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# ── Load data ─────────────────────────────────────────────────────────────────
def _load_json(fname):
    return json.loads((DATA_DIR / fname).read_text())

THRESHOLDS  = _load_json("cefr_thresholds.json")
CONNECTORS  = _load_json("connector_taxonomy.json")
LEVEL_ORDER = THRESHOLDS["progression_rules"]["level_order"]


# ── Connector detection ───────────────────────────────────────────────────────
def detect_connectors(transcript: str) -> dict:
    """
    Scan transcript for discourse connectors.

    Returns:
        found: {type_key: [matched_words]}
        missing_types: [type_key]  — types not used at all
        types_used_count: int
        discourse_score: float  0–100
    """
    text_lower = transcript.lower()
    found = {}

    for type_key, type_data in CONNECTORS["types"].items():
        matched = []
        for phrase in type_data["words"]:
            pattern = r'\b' + re.escape(phrase) + r'\b'
            if re.search(pattern, text_lower):
                matched.append(phrase)
        if matched:
            found[type_key] = matched

    all_types   = list(CONNECTORS["types"].keys())
    missing     = [t for t in all_types if t not in found]
    types_count = len(found)

    # Discourse score: % of connector type variety (8 types max = 100)
    discourse_score = round(min(100.0, (types_count / len(all_types)) * 100), 1)

    return {
        "found":             found,
        "missing_types":     missing,
        "types_used_count":  types_count,
        "discourse_score":   discourse_score
    }


# ── Component normalization ────────────────────────────────────────────────────
def _normalize_wpm(wpm: float, level: str) -> float:
    """
    Score 0–100. 100 = at or above WPM target for level.
    Penalized linearly below min, capped at 100 above target.
    """
    cfg     = THRESHOLDS["levels"][level]
    wpm_min = cfg["wpm_min"]
    wpm_tgt = cfg["wpm_target"]
    if wpm <= 0:
        return 0.0
    if wpm >= wpm_tgt:
        return 100.0
    if wpm < wpm_min * 0.5:
        return 0.0
    # Linear between 0 and 100 from (wpm_min*0.5) to wpm_tgt
    return round(max(0.0, min(100.0, (wpm - wpm_min * 0.5) / (wpm_tgt - wpm_min * 0.5) * 100)), 1)


def _normalize_pauses(pause_rate: float, level: str) -> float:
    """
    Score 0–100. 100 = pause rate at or below threshold for level.
    Penalized linearly above threshold.
    """
    cfg       = THRESHOLDS["levels"][level]
    max_rate  = cfg["pause_per_min_max"]
    if pause_rate <= 0:
        return 100.0
    if pause_rate <= max_rate * 0.5:
        return 100.0
    if pause_rate >= max_rate * 2.0:
        return 0.0
    # Linear from 100 → 0 between 0.5× and 2× the max
    ratio = (pause_rate - max_rate * 0.5) / (max_rate * 2.0 - max_rate * 0.5)
    return round(max(0.0, 100.0 - ratio * 100.0), 1)


def _normalize_fillers(filler_rate: float, level: str) -> float:
    """
    Score 0–100. 100 = zero fillers.
    """
    cfg      = THRESHOLDS["levels"][level]
    max_rate = cfg["filler_per_min_max"]
    if filler_rate <= 0:
        return 100.0
    if filler_rate >= max_rate * 2.0:
        return 0.0
    ratio = filler_rate / (max_rate * 2.0)
    return round(max(0.0, 100.0 - ratio * 100.0), 1)


# ── Composite fluency score ────────────────────────────────────────────────────
def compute_fluency_score(
    wpm: float,
    pause_rate: float,
    filler_rate: float,
    level: str,
    transcript: str = ""
) -> dict:
    """
    Returns:
        fluency_score:       float  0–100
        wpm_component:       float  0–100
        pause_component:     float  0–100
        filler_component:    float  0–100
        connector_data:      dict
        grade:               str   (Excellent / Good / Developing / Needs Work)
        interpretation:      str
    """
    wpm_c    = _normalize_wpm(wpm, level)
    pause_c  = _normalize_pauses(pause_rate, level)
    filler_c = _normalize_fillers(filler_rate, level)

    score = round(0.40 * wpm_c + 0.30 * pause_c + 0.30 * filler_c, 1)

    # Connector analysis
    connector_data = detect_connectors(transcript) if transcript else {
        "found": {}, "missing_types": [], "types_used_count": 0, "discourse_score": 0
    }

    # Grade
    if score >= 80:
        grade, interpretation = "Excellent", "Your fluency metrics are at or above your current CEFR target."
    elif score >= 65:
        grade, interpretation = "Good", "Your fluency is developing well. Focus on the lowest-scoring component."
    elif score >= 45:
        grade, interpretation = "Developing", "There is clear room to improve. Review the corrections and repeat the scenario."
    else:
        grade, interpretation = "Needs Work", "Significant gaps identified. Study the corrections and practise the target structures."

    return {
        "fluency_score":    score,
        "wpm_component":    wpm_c,
        "pause_component":  pause_c,
        "filler_component": filler_c,
        "connector_data":   connector_data,
        "grade":            grade,
        "interpretation":   interpretation
    }


# ── CEFR level assessment ──────────────────────────────────────────────────────
def assess_cefr_level(
    wpm: float,
    pause_rate: float,
    filler_rate: float,
    fluency_score: float
) -> dict:
    """
    Cross-reference acoustic metrics against all CEFR levels.

    Returns:
        assessed_level:  str   (e.g. "B1")
        confidence:      float 0–1
        evidence:        dict  {wpm_verdict, pause_verdict, filler_verdict}
        score_band:      str   (e.g. "B1 (52–65)")
    """
    best_level    = "A1"
    best_match    = 0.0

    for level in LEVEL_ORDER:
        cfg = THRESHOLDS["levels"][level]
        score_min = cfg["score_min"]
        score_max = cfg["score_max"]

        # How well does the score sit within this band?
        if score_min <= fluency_score <= score_max:
            # Perfect band match — also check WPM proximity
            wpm_prox = 1.0 - abs(wpm - cfg["wpm_target"]) / max(cfg["wpm_target"], 1)
            match = 0.7 + 0.3 * max(0.0, wpm_prox)
        elif fluency_score < score_min:
            gap = score_min - fluency_score
            match = max(0.0, 0.5 - gap / 50.0)
        else:
            gap = fluency_score - score_max
            match = max(0.0, 0.5 - gap / 50.0)

        if match > best_match:
            best_match = match
            best_level = level

    cfg = THRESHOLDS["levels"][best_level]
    evidence = {
        "wpm_verdict":    _verdict(wpm, cfg["wpm_min"], cfg["wpm_max"]),
        "pause_verdict":  _verdict_inverse(pause_rate, cfg["pause_per_min_max"]),
        "filler_verdict": _verdict_inverse(filler_rate, cfg["filler_per_min_max"])
    }

    return {
        "assessed_level": best_level,
        "confidence":     round(min(1.0, best_match), 2),
        "evidence":       evidence,
        "score_band":     f"{best_level} ({cfg['score_min']}–{cfg['score_max']})"
    }


def _verdict(value, v_min, v_max):
    if value < v_min:
        return "below range"
    elif value > v_max:
        return "above range"
    return "within range"

def _verdict_inverse(value, v_max):
    if value <= v_max:
        return "within target"
    return f"above target ({v_max:.1f}/min)"


# ── Progression logic ─────────────────────────────────────────────────────────
def check_level_progression(sessions: list, current_level: str) -> dict:
    """
    Analyse recent sessions to determine if level should advance or drop.

    Args:
        sessions:      List of session dicts (most recent first)
        current_level: Current CEFR level string

    Returns:
        action:        "advance" | "drop" | "maintain"
        reason:        str
        new_level:     str
    """
    rules = THRESHOLDS["progression_rules"]
    adv_n  = rules["advance_after_sessions"]
    adv_pct = rules["advance_threshold_pct"]
    drop_n  = rules["drop_after_sessions"]
    drop_pct = rules["drop_threshold_pct"]
    order  = LEVEL_ORDER
    idx    = order.index(current_level) if current_level in order else 0
    cfg    = THRESHOLDS["levels"][current_level]

    # Get recent sessions at this level
    same_level = [s for s in sessions if s.get("cefr_level") == current_level]

    if len(same_level) < max(adv_n, drop_n):
        return {"action": "maintain", "reason": "Not enough sessions at this level yet.", "new_level": current_level}

    recent_scores = [s.get("fluency_score", 0) for s in same_level[:adv_n]]
    score_threshold_high = cfg["score_max"] * adv_pct
    score_threshold_low  = cfg["score_min"] * drop_pct

    if all(s >= score_threshold_high for s in recent_scores[:adv_n]):
        if idx < len(order) - 1:
            new_level = order[idx + 1]
            return {
                "action":    "advance",
                "reason":    f"Scored above {score_threshold_high:.0f} for {adv_n} consecutive sessions.",
                "new_level": new_level
            }

    recent_drop = [s.get("fluency_score", 0) for s in same_level[:drop_n]]
    if all(s < score_threshold_low for s in recent_drop[:drop_n]):
        if idx > 0:
            new_level = order[idx - 1]
            return {
                "action":    "drop",
                "reason":    f"Scored below {score_threshold_low:.0f} for {drop_n} consecutive sessions.",
                "new_level": new_level
            }

    return {"action": "maintain", "reason": "Continuing at current level.", "new_level": current_level}
