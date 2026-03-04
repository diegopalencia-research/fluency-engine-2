"""
core/rule_feedback.py
Rule-based grammar correction engine - NO AI REQUIRED

Uses pattern matching to detect common grammar errors based on CEFR level.
Provides corrections in Finishing School protocol format.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Tuple

DATA_DIR = Path(__file__).parent.parent / "data"

# Load grammar patterns
with open(DATA_DIR / "grammar_patterns.json") as f:
    GRAMMAR_DATA = json.load(f)
    GRAMMAR_PATTERNS = GRAMMAR_DATA["patterns"]
    CORRECTION_TEMPLATES = GRAMMAR_DATA["correction_templates"]

# Load connector taxonomy
with open(DATA_DIR / "connector_taxonomy.json") as f:
    CONNECTOR_DATA = json.load(f)

# Load filler patterns
with open(DATA_DIR / "filler_patterns.json") as f:
    FILLER_PATTERNS = json.load(f)["fillers"]


def detect_grammar_errors(transcript: str, level: str) -> List[Dict]:
    """
    Detect grammar errors using pattern matching.
    Returns list of error dicts with original, corrected, rule, and explanation.
    """
    errors = []
    transcript_lower = transcript.lower()
    
    # Get patterns appropriate for this CEFR level
    level_order = ["A1", "A2", "B1", "B2", "C1", "C2"]
    current_idx = level_order.index(level) if level in level_order else 2
    
    for pattern_key, pattern_data in GRAMMAR_PATTERNS.items():
        # Check if pattern is appropriate for this level
        pattern_levels = pattern_data.get("cefr_levels", [])
        pattern_idx = min(level_order.index(l) for l in pattern_levels if l in level_order) if pattern_levels else 0
        
        # Only check patterns at or below current level
        if pattern_idx > current_idx:
            continue
            
        for regex_pattern in pattern_data.get("patterns", []):
            try:
                matches = list(re.finditer(regex_pattern, transcript_lower, re.IGNORECASE))
                for match in matches:
                    # Get the matched text
                    original = match.group(0)
                    
                    # Try to generate a correction
                    corrected = generate_correction(original, pattern_key, match)
                    
                    if corrected and corrected != original:
                        template = CORRECTION_TEMPLATES.get(pattern_key, {})
                        errors.append({
                            "original": original,
                            "corrected": corrected,
                            "rule": pattern_data.get("label", pattern_key),
                            "explanation": template.get("explanation", ""),
                            "example": template.get("example", ""),
                            "practice": template.get("practice", ""),
                            "severity": pattern_data.get("severity", "medium"),
                            "pattern_key": pattern_key
                        })
            except re.error:
                continue
    
    # Remove duplicates and sort by severity
    seen = set()
    unique_errors = []
    for e in errors:
        key = e["original"].lower()
        if key not in seen:
            seen.add(key)
            unique_errors.append(e)
    
    severity_order = {"high": 0, "medium": 1, "low": 2}
    unique_errors.sort(key=lambda x: severity_order.get(x["severity"], 1))
    
    return unique_errors[:6]  # Return top 6 errors


def generate_correction(original: str, pattern_key: str, match) -> str:
    """Generate a corrected version based on the error type."""
    original_lower = original.lower()
    
    corrections = {
        "third_person_s": lambda: re.sub(r'\b(he|she|it)\s+([a-z]+)(?<!s)\b', 
                                         lambda m: f"{m.group(1)} {m.group(2)}s" if not m.group(2).endswith('s') else m.group(0), 
                                         original_lower),
        "past_simple_regular": lambda: re.sub(r'\b([a-z]+)(?<!ed)\s+(yesterday|last)',
                                              lambda m: f"{m.group(1)}ed {m.group(2)}",
                                              original_lower),
        "article_usage": lambda: re.sub(r'\b(i am|you are|he is|she is|it is|we are|they are)\s+([a-z]+)\b(?!\s+(?:who|that|from|and|or))',
                                        lambda m: f"{m.group(1)} a {m.group(2)}",
                                        original_lower),
        "plural_nouns": lambda: re.sub(r'\b(two|three|four|five|many|several|some|a few)\s+([a-z]+)(?<!s)\b',
                                       lambda m: f"{m.group(1)} {m.group(2)}s",
                                       original_lower),
        "subject_verb_agreement": lambda: fix_subject_verb_agreement(original_lower),
        "double_negative": lambda: fix_double_negative(original_lower),
        "modal_verbs": lambda: re.sub(r'\b(can|could|should|would|might|may|must)\s+to\s+',
                                      lambda m: f"{m.group(1)} ",
                                      original_lower),
        "question_formation": lambda: fix_question_formation(original_lower),
    }
    
    if pattern_key in corrections:
        try:
            return corrections[pattern_key]()
        except:
            pass
    
    # Default: return original with a suggestion
    return original


def fix_subject_verb_agreement(text: str) -> str:
    """Fix common subject-verb agreement errors."""
    fixes = [
        (r'\b(they|we|you|the people|my parents|my friends)\s+is\b', r'\1 are'),
        (r'\b(they|we|you|the people|my parents|my friends)\s+was\b', r'\1 were'),
        (r'\b(they|we|you|the people|my parents|my friends)\s+has\b', r'\1 have'),
        (r'\b(they|we|you|the people|my parents|my friends)\s+does\b', r'\1 do'),
        (r'\b(he|she|it|the person|my friend)\s+are\b', r'\1 is'),
        (r'\b(he|she|it|the person|my friend)\s+were\b', r'\1 was'),
        (r'\b(he|she|it|the person|my friend)\s+have\b', r'\1 has'),
        (r'\b(he|she|it|the person|my friend)\s+do\b', r'\1 does'),
    ]
    
    result = text
    for pattern, replacement in fixes:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def fix_double_negative(text: str) -> str:
    """Fix double negative errors."""
    fixes = [
        (r"\bdon't have nothing\b", "don't have anything"),
        (r"\bdon't know nobody\b", "don't know anybody"),
        (r"\bdon't see nothing\b", "don't see anything"),
        (r"\bdoesn't have nothing\b", "doesn't have anything"),
        (r"\bdoesn't know nobody\b", "doesn't know anybody"),
        (r"\bcan't find nothing\b", "can't find anything"),
    ]
    
    result = text
    for pattern, replacement in fixes:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def fix_question_formation(text: str) -> str:
    """Fix question word order errors."""
    fixes = [
        (r"^(you|we|they|he|she|it)\s+are\s*\?", r"Are \1?"),
        (r"^(you|we|they)\s+do\s*\?", r"Do \1?"),
        (r"^(he|she|it)\s+does\s*\?", r"Does \1?"),
        (r"^(you|we|they|he|she|it)\s+can\s*\?", r"Can \1?"),
        (r"^(you|we|they|he|she|it)\s+will\s*\?", r"Will \1?"),
    ]
    
    result = text
    for pattern, replacement in fixes:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def detect_connectors_local(transcript: str) -> Dict:
    """
    Detect discourse connectors in transcript.
    Local version that doesn't require external API.
    """
    text_lower = transcript.lower()
    found = {}
    
    for type_key, type_data in CONNECTOR_DATA["types"].items():
        matched = []
        for phrase in type_data["words"]:
            pattern = r'\b' + re.escape(phrase) + r'\b'
            if re.search(pattern, text_lower):
                matched.append(phrase)
        if matched:
            found[type_key] = matched
    
    all_types = list(CONNECTOR_DATA["types"].keys())
    missing = [t for t in all_types if t not in found]
    types_count = len(found)
    
    # Discourse score: % of connector type variety (8 types max = 100)
    discourse_score = round(min(100.0, (types_count / len(all_types)) * 100), 1)
    
    # Find strongest missing connector for the level
    strongest_missing = missing[0] if missing else ""
    
    # Generate example sentence for strongest missing
    example_sentence = ""
    if strongest_missing:
        examples = {
            "sequencing": "First, I woke up early. Then, I had breakfast.",
            "contrast": "I enjoy the city. However, it can be noisy.",
            "cause_effect": "It was raining, so I took an umbrella.",
            "addition": "The food was delicious. Furthermore, the service was excellent.",
            "exemplification": "I enjoy outdoor activities, for example, hiking and cycling.",
            "concession": "The task was difficult. Nevertheless, I completed it.",
            "summary": "In conclusion, this was a valuable experience.",
            "hedging": "It seems that the situation is improving."
        }
        example_sentence = examples.get(strongest_missing, "")
    
    return {
        "found": found,
        "missing_types": missing,
        "types_used_count": types_count,
        "discourse_score": discourse_score,
        "strongest_missing": strongest_missing,
        "example_sentence": example_sentence
    }


def detect_fillers_local(transcript: str) -> Dict:
    """
    Detect filler words in transcript.
    Returns filler data similar to the original analyze.py.
    """
    by_type = {}
    instances = []
    
    for key, meta in FILLER_PATTERNS.items():
        pattern = re.compile(meta["pattern"], re.IGNORECASE)
        matches = pattern.findall(transcript)
        if matches:
            by_type[key] = {
                "count": len(matches),
                "label": meta["label"],
                "severity": meta["severity"]
            }
            instances.extend(matches)
    
    # Find worst offender
    worst_offender = ""
    worst_count = 0
    for key, data in by_type.items():
        if data["count"] > worst_count:
            worst_count = data["count"]
            worst_offender = data["label"]
    
    # Replacement tips
    tips = {
        "uh": "Try pausing silently instead of saying 'uh'",
        "um": "Take a breath and pause - silence is better than 'um'",
        "like": "Use 'such as' for examples, or simply pause",
        "you know": "Remove entirely - trust your listener understands",
        "basically": "Use only when simplifying complex ideas",
        "literally": "Remove unless something is truly literal",
        "actually": "Remove - it rarely adds meaning",
        "so": "Avoid starting sentences with 'so'",
        "right": "Remove tag questions - state your point confidently",
        "i mean": "Remove and get straight to your point",
        "kind of": "Use 'somewhat' or remove entirely",
        "sort of": "Use 'rather' or remove entirely"
    }
    
    return {
        "total_count": sum(v["count"] for v in by_type.values()),
        "by_type": by_type,
        "instances": instances,
        "worst_offender": worst_offender,
        "replacement_tip": tips.get(worst_offender.split()[0], "Try to reduce this filler word")
    }


def generate_rule_based_feedback(
    transcript: str,
    scenario: dict,
    analysis: dict,
    level: str
) -> Dict:
    """
    Generate comprehensive feedback using only rule-based detection.
    NO AI REQUIRED - works completely offline.
    
    Returns dict in same format as AI-based feedback for compatibility.
    """
    # Detect grammar errors
    grammar_errors = detect_grammar_errors(transcript, level)
    
    # Detect connectors
    connector_data = detect_connectors_local(transcript)
    
    # Detect fillers
    filler_data = detect_fillers_local(transcript)
    
    # Build sentence corrections
    sentence_corrections = []
    for error in grammar_errors:
        sentence_corrections.append({
            "original": error["original"],
            "corrected": error["corrected"],
            "rule": error["rule"],
            "repeat_prompt": f"Please say: {error['corrected']}"
        })
    
    # Generate grammar patterns found list
    grammar_patterns_found = list(set(e["pattern_key"] for e in grammar_errors))
    
    # Generate narrative coaching
    narrative = generate_narrative_coaching(
        analysis, connector_data, filler_data, grammar_errors, level
    )
    
    # Task relevance assessment
    task_relevance = assess_task_relevance(transcript, scenario)
    
    return {
        "sentence_corrections": sentence_corrections,
        "connector_feedback": {
            "types_used": list(connector_data["found"].keys()),
            "strongest_missing": connector_data["strongest_missing"],
            "example_sentence": connector_data["example_sentence"]
        },
        "filler_feedback": {
            "worst_offender": filler_data["worst_offender"],
            "replacement_tip": filler_data["replacement_tip"]
        },
        "narrative_coaching": narrative,
        "grammar_patterns_found": grammar_patterns_found,
        "task_relevance": task_relevance,
        "error": None
    }


def generate_narrative_coaching(analysis, connector_data, filler_data, grammar_errors, level):
    """Generate coaching summary based on metrics."""
    parts = []
    
    # Overall impression based on fluency score
    score = analysis.get("fluency_score", 50)
    if score >= 80:
        parts.append("Excellent fluency demonstration!")
    elif score >= 65:
        parts.append("Good fluency with solid control.")
    elif score >= 45:
        parts.append("Developing fluency with room to improve.")
    else:
        parts.append("Keep practicing - improvement comes with repetition.")
    
    # Key strength
    wpm = analysis.get("wpm", 100)
    pause_rate = analysis.get("pause_rate", 5)
    filler_rate = analysis.get("filler_rate", 3)
    
    if wpm >= 120:
        parts.append("Your speaking pace is strong.")
    elif pause_rate < 5:
        parts.append("You maintain good flow with minimal pausing.")
    elif filler_rate < 2:
        parts.append("You use very few filler words.")
    elif connector_data["types_used_count"] >= 3:
        parts.append("Good variety of connecting words.")
    else:
        parts.append("Your response addressed the task.")
    
    # Priority improvement
    priorities = []
    if filler_rate > 4:
        priorities.append("reducing filler words")
    if pause_rate > 8:
        priorities.append("smoother transitions between ideas")
    if connector_data["types_used_count"] < 2:
        priorities.append("using more connecting words")
    if len(grammar_errors) > 3:
        priorities.append("grammar accuracy")
    
    if priorities:
        parts.append(f"Focus next on: {', '.join(priorities[:2])}.")
    else:
        parts.append("Continue practicing to maintain your progress.")
    
    return " ".join(parts)


def assess_task_relevance(transcript: str, scenario: dict) -> str:
    """Simple assessment of whether response addresses the scenario."""
    prompt = scenario.get("prompt", "").lower()
    transcript_lower = transcript.lower()
    
    # Extract key words from prompt
    key_words = [w for w in prompt.split() if len(w) > 4 and w not in 
                 ["describe", "explain", "discuss", "talk", "about", "would", "should", "could"]]
    
    # Count matches
    matches = sum(1 for word in key_words if word in transcript_lower)
    
    if matches >= 3 or len(transcript.split()) > 30:
        return "Response directly addresses the scenario prompt."
    elif matches >= 1:
        return "Response partially addresses the scenario."
    else:
        return "Response may not fully address the scenario topic."


# For testing
if __name__ == "__main__":
    test_transcript = "Yesterday I go to the store and buy some food. She don't like it. We was very happy."
    result = detect_grammar_errors(test_transcript, "A2")
    print(json.dumps(result, indent=2))
