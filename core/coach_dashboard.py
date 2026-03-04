"""
core/coach_dashboard.py
Coach Dashboard functionality for managing students and scenarios.

Features:
- View all students and their progress
- See common mistakes across students
- Identify areas of opportunity
- Manage scenario library
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
SESSIONS_DIR = BASE_DIR / "sessions"
MEMORY_DIR = BASE_DIR / "memory"


def get_all_students() -> List[Dict]:
    """Get list of all students with their session counts."""
    students = []
    
    if not SESSIONS_DIR.exists():
        return students
    
    for session_file in SESSIONS_DIR.glob("*_sessions.json"):
        username = session_file.stem.replace("_sessions", "")
        
        try:
            with open(session_file) as f:
                sessions = json.load(f)
            
            # Get latest session info
            latest_session = sessions[-1] if sessions else {}
            
            # Load error memory
            memory_file = MEMORY_DIR / f"{username}_memory.json"
            error_memory = {}
            if memory_file.exists():
                with open(memory_file) as f:
                    error_memory = json.load(f)
            
            students.append({
                "username": username,
                "total_sessions": len(sessions),
                "current_level": latest_session.get("cefr_level", "B1"),
                "last_session": latest_session.get("timestamp", "Never"),
                "avg_score": sum(s.get("fluency_score", 0) for s in sessions) / len(sessions) if sessions else 0,
                "avg_wpm": sum(s.get("wpm", 0) for s in sessions) / len(sessions) if sessions else 0,
                "top_errors": get_top_errors(error_memory, 3),
                "improving": error_memory.get("wpm_trend", "stable") == "improving"
            })
        except Exception as e:
            print(f"Error loading student {username}: {e}")
    
    # Sort by total sessions (most active first)
    students.sort(key=lambda x: x["total_sessions"], reverse=True)
    return students


def get_top_errors(error_memory: Dict, n: int = 5) -> List[Dict]:
    """Get top N errors from error memory."""
    grammar_errors = error_memory.get("grammar_errors", {})
    
    sorted_errors = sorted(
        [(k, v) for k, v in grammar_errors.items()],
        key=lambda x: x[1],
        reverse=True
    )
    
    return [
        {"pattern": e[0], "count": e[1], "label": e[0].replace("_", " ").title()}
        for e in sorted_errors[:n]
    ]


def get_common_mistakes_across_students() -> Dict:
    """Analyze common mistakes across all students."""
    all_grammar_errors = Counter()
    all_fillers = Counter()
    all_missing_connectors = Counter()
    
    level_distribution = Counter()
    total_students = 0
    
    if not MEMORY_DIR.exists():
        return {
            "grammar_errors": [],
            "fillers": [],
            "missing_connectors": [],
            "level_distribution": {},
            "total_students": 0
        }
    
    for memory_file in MEMORY_DIR.glob("*_memory.json"):
        try:
            with open(memory_file) as f:
                memory = json.load(f)
            
            total_students += 1
            
            # Grammar errors
            for pattern, count in memory.get("grammar_errors", {}).items():
                all_grammar_errors[pattern] += count
            
            # Fillers
            for filler, count in memory.get("habitual_fillers", {}).items():
                all_fillers[filler] += count
            
            # Missing connectors
            for connector in memory.get("missing_connectors", []):
                all_missing_connectors[connector] += 1
            
            # Level from level history
            level_history = memory.get("level_history", [])
            if level_history:
                level_distribution[level_history[-1]] += 1
                
        except Exception as e:
            print(f"Error analyzing memory file: {e}")
    
    return {
        "grammar_errors": [
            {"pattern": k, "count": v, "label": k.replace("_", " ").title()}
            for k, v in all_grammar_errors.most_common(10)
        ],
        "fillers": [
            {"filler": k, "count": v, "label": k.replace("_", " ").title()}
            for k, v in all_fillers.most_common(10)
        ],
        "missing_connectors": [
            {"connector": k, "count": v, "label": k.replace("_", " ").title()}
            for k, v in all_missing_connectors.most_common(8)
        ],
        "level_distribution": dict(level_distribution),
        "total_students": total_students
    }


def get_areas_of_opportunity() -> List[Dict]:
    """Identify key areas where students need improvement."""
    common_mistakes = get_common_mistakes_across_students()
    
    opportunities = []
    
    # Grammar opportunities
    for error in common_mistakes["grammar_errors"][:5]:
        opportunities.append({
            "type": "grammar",
            "area": error["label"],
            "affected_students": error["count"],
            "priority": "high" if error["count"] > 5 else "medium",
            "suggestion": get_grammar_suggestion(error["pattern"])
        })
    
    # Connector opportunities
    for connector in common_mistakes["missing_connectors"][:3]:
        opportunities.append({
            "type": "connector",
            "area": connector["label"],
            "affected_students": connector["count"],
            "priority": "medium",
            "suggestion": get_connector_suggestion(connector["connector"])
        })
    
    # Filler opportunities
    if common_mistakes["fillers"]:
        top_filler = common_mistakes["fillers"][0]
        opportunities.append({
            "type": "filler",
            "area": top_filler["label"],
            "affected_students": top_filler["count"],
            "priority": "low",
            "suggestion": f"Practice reducing '{top_filler['filler']}' in speech"
        })
    
    return opportunities


def get_grammar_suggestion(pattern: str) -> str:
    """Get teaching suggestion for a grammar pattern."""
    suggestions = {
        "third_person_s": "Drill: He/She/It + verb+s (works, plays, goes)",
        "past_simple_regular": "Practice adding -ed to regular verbs",
        "past_simple_irregular": "Memorize common irregular verbs: go-went, see-saw, take-took",
        "present_perfect": "Practice: have/has + past participle",
        "article_usage": "Review when to use a/an/the vs. no article",
        "plural_nouns": "Practice adding -s/-es to plural nouns",
        "prepositions_time": "Review: on + days, in + months, at + times",
        "prepositions_place": "Review common preposition combinations",
        "subject_verb_agreement": "Drill: plural subjects = plural verbs",
        "comparative": "Review: -er for short words, more + long words",
        "superlative": "Review: -est for short words, most + long words",
        "modal_verbs": "Practice: modal + base verb (no 'to')",
        "question_formation": "Drill: Auxiliary + subject + verb order",
        "double_negative": "Teach: one negative per clause only",
        "countable_uncountable": "Practice: many + countable, much + uncountable",
        "conditional_first": "Drill: If + present, will + verb",
        "word_order": "Practice SVO word order in English"
    }
    return suggestions.get(pattern, f"Review: {pattern.replace('_', ' ')}")


def get_connector_suggestion(connector_type: str) -> str:
    """Get teaching suggestion for a connector type."""
    suggestions = {
        "sequencing": "Teach: first, then, after that, finally",
        "contrast": "Teach: however, although, on the other hand",
        "cause_effect": "Teach: because, so, therefore, as a result",
        "addition": "Teach: furthermore, in addition, moreover",
        "exemplification": "Teach: for example, for instance, such as",
        "concession": "Teach: admittedly, nevertheless, however",
        "summary": "Teach: in conclusion, to sum up, overall",
        "hedging": "Teach: it seems that, arguably, to some extent"
    }
    return suggestions.get(connector_type, f"Practice using {connector_type} connectors")


def get_student_detail(username: str) -> Optional[Dict]:
    """Get detailed information about a specific student."""
    session_file = SESSIONS_DIR / f"{username}_sessions.json"
    memory_file = MEMORY_DIR / f"{username}_memory.json"
    
    if not session_file.exists():
        return None
    
    try:
        with open(session_file) as f:
            sessions = json.load(f)
        
        memory = {}
        if memory_file.exists():
            with open(memory_file) as f:
                memory = json.load(f)
        
        # Calculate progress metrics
        if len(sessions) >= 2:
            recent_scores = [s.get("fluency_score", 0) for s in sessions[-5:]]
            earlier_scores = [s.get("fluency_score", 0) for s in sessions[:5]]
            score_trend = "improving" if sum(recent_scores) > sum(earlier_scores) else "stable"
            
            recent_wpm = [s.get("wpm", 0) for s in sessions[-5:]]
            earlier_wpm = [s.get("wpm", 0) for s in sessions[:5]]
            wpm_trend = "improving" if sum(recent_wpm) > sum(earlier_wpm) else "stable"
        else:
            score_trend = "insufficient_data"
            wpm_trend = "insufficient_data"
        
        return {
            "username": username,
            "total_sessions": len(sessions),
            "sessions": sessions,
            "memory": memory,
            "score_trend": score_trend,
            "wpm_trend": wpm_trend,
            "avg_score": sum(s.get("fluency_score", 0) for s in sessions) / len(sessions) if sessions else 0,
            "avg_wpm": sum(s.get("wpm", 0) for s in sessions) / len(sessions) if sessions else 0,
            "avg_filler_rate": sum(s.get("filler_rate", 0) for s in sessions) / len(sessions) if sessions else 0,
            "avg_pause_rate": sum(s.get("pause_rate", 0) for s in sessions) / len(sessions) if sessions else 0,
            "level_progression": memory.get("level_history", []),
            "top_errors": get_top_errors(memory, 5),
            "habitual_fillers": [
                {"filler": k, "count": v}
                for k, v in sorted(memory.get("habitual_fillers", {}).items(), key=lambda x: -x[1])[:5]
            ],
            "missing_connectors": memory.get("missing_connectors", [])
        }
    except Exception as e:
        print(f"Error loading student detail: {e}")
        return None


def get_class_statistics() -> Dict:
    """Get overall class statistics."""
    students = get_all_students()
    
    if not students:
        return {
            "total_students": 0,
            "total_sessions": 0,
            "avg_sessions_per_student": 0,
            "avg_score": 0,
            "avg_wpm": 0,
            "most_active_student": None,
            "highest_scoring_student": None
        }
    
    total_sessions = sum(s["total_sessions"] for s in students)
    avg_score = sum(s["avg_score"] for s in students) / len(students)
    avg_wpm = sum(s["avg_wpm"] for s in students) / len(students)
    
    most_active = max(students, key=lambda x: x["total_sessions"])
    highest_scoring = max(students, key=lambda x: x["avg_score"])
    
    return {
        "total_students": len(students),
        "total_sessions": total_sessions,
        "avg_sessions_per_student": total_sessions / len(students),
        "avg_score": round(avg_score, 1),
        "avg_wpm": round(avg_wpm, 1),
        "most_active_student": {
            "username": most_active["username"],
            "sessions": most_active["total_sessions"]
        },
        "highest_scoring_student": {
            "username": highest_scoring["username"],
            "score": round(highest_scoring["avg_score"], 1)
        }
    }


def export_class_data() -> str:
    """Export all class data as CSV for external analysis."""
    import csv
    import io
    
    students = get_all_students()
    
    if not students:
        return ""
    
    fieldnames = [
        "username", "total_sessions", "current_level", "avg_score",
        "avg_wpm", "last_session", "improving"
    ]
    
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    
    for student in students:
        row = {k: student.get(k, "") for k in fieldnames}
        writer.writerow(row)
    
    return buf.getvalue()


# For testing
if __name__ == "__main__":
    print("Students:")
    for s in get_all_students()[:5]:
        print(f"  {s['username']}: {s['total_sessions']} sessions, level {s['current_level']}")
    
    print("\nCommon mistakes:")
    print(json.dumps(get_common_mistakes_across_students(), indent=2))
    
    print("\nAreas of opportunity:")
    for opp in get_areas_of_opportunity()[:5]:
        print(f"  {opp['area']} ({opp['type']}): {opp['suggestion']}")
