"""
core/scenario_manager.py
Scenario management system - NO AI REQUIRED

Loads scenarios from pre-built library. Coaches can add/edit scenarios
by modifying the scenario_library.json file.
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional

DATA_DIR = Path(__file__).parent.parent / "data"
SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"
SCENARIOS_DIR.mkdir(exist_ok=True)

# Load scenario library
with open(DATA_DIR / "scenario_library.json") as f:
    SCENARIO_LIBRARY = json.load(f)["scenarios"]

SCENARIO_TYPES = {
    "free_response": {"label": "Free Response", "min_level": "A1", "seconds": 30},
    "narrative": {"label": "Narrative", "min_level": "A2", "seconds": 60},
    "retell": {"label": "Retell", "min_level": "A2", "seconds": 60},
    "opinion": {"label": "Opinion", "min_level": "B1", "seconds": 60},
    "problem_solve": {"label": "Problem Solving", "min_level": "B1", "seconds": 60},
    "comparison": {"label": "Comparison", "min_level": "B2", "seconds": 75},
    "instruction_follow": {"label": "Instruction Following", "min_level": "A2", "seconds": 45},
    "debate_opener": {"label": "Debate Opener", "min_level": "B2", "seconds": 60},
}

LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


def get_available_types(level: str) -> List[str]:
    """Return scenario types available at or below the given CEFR level."""
    idx = LEVEL_ORDER.index(level) if level in LEVEL_ORDER else 2
    return [k for k, v in SCENARIO_TYPES.items()
            if LEVEL_ORDER.index(v["min_level"]) <= idx]


def get_scenarios_for_level(level: str, scenario_type: Optional[str] = None) -> List[Dict]:
    """
    Get all scenarios for a specific CEFR level.
    Optionally filter by scenario type.
    """
    level_scenarios = SCENARIO_LIBRARY.get(level, {})
    
    if scenario_type and scenario_type in level_scenarios:
        return level_scenarios[scenario_type]
    elif scenario_type == "all" or scenario_type is None:
        # Return all scenarios for this level
        all_scenarios = []
        for stype, scenarios in level_scenarios.items():
            for s in scenarios:
                s_copy = s.copy()
                s_copy["scenario_type"] = stype
                s_copy["scenario_type_label"] = SCENARIO_TYPES.get(stype, {}).get("label", stype)
                all_scenarios.append(s_copy)
        return all_scenarios
    else:
        return []


def get_scenario(
    level: str,
    scenario_type: Optional[str] = None,
    error_memory: Optional[Dict] = None,
    used_ids: Optional[List[str]] = None
) -> Dict:
    """
    Get a scenario for the user.
    
    Args:
        level: CEFR level (A1-C2)
        scenario_type: Optional specific scenario type
        error_memory: User's error memory for personalization hints
        used_ids: List of scenario IDs already used (to avoid repetition)
    
    Returns:
        Scenario dict with all required fields
    """
    used_ids = used_ids or []
    
    # Get available types for this level
    available_types = get_available_types(level)
    
    # Filter by requested type if specified
    if scenario_type and scenario_type in available_types:
        selected_type = scenario_type
    elif scenario_type == "Auto" or scenario_type is None:
        selected_type = random.choice(available_types)
    else:
        selected_type = random.choice(available_types)
    
    # Get scenarios for this level and type
    scenarios = get_scenarios_for_level(level, selected_type)
    
    if not scenarios:
        # Fallback to free response if no scenarios found
        scenarios = get_scenarios_for_level(level, "free_response")
    
    if not scenarios:
        # Ultimate fallback - create a generic scenario
        return create_generic_scenario(level, selected_type)
    
    # Filter out recently used scenarios
    unused_scenarios = [s for s in scenarios if s.get("id") not in used_ids]
    
    # If all scenarios have been used, reset
    if not unused_scenarios:
        unused_scenarios = scenarios
    
    # Select random scenario
    scenario = random.choice(unused_scenarios).copy()
    
    # Add metadata
    scenario["scenario_type"] = selected_type
    scenario["scenario_type_label"] = SCENARIO_TYPES.get(selected_type, {}).get("label", selected_type)
    scenario["level"] = level
    
    # Add personalization hint based on error memory
    if error_memory:
        hint = generate_personalization_hint(error_memory)
        if hint:
            scenario["personalization_hint"] = hint
    
    return scenario


def create_generic_scenario(level: str, scenario_type: str) -> Dict:
    """Create a generic scenario if no specific ones are available."""
    type_label = SCENARIO_TYPES.get(scenario_type, {}).get("label", "Practice")
    duration = SCENARIO_TYPES.get(scenario_type, {}).get("seconds", 60)
    
    prompts = {
        "free_response": f"Talk about a topic you are familiar with at {level} level.",
        "narrative": "Tell a short story about something that happened to you.",
        "retell": "Summarize a story, movie, or article you recently experienced.",
        "opinion": "Share your opinion on an important topic and explain why.",
        "problem_solve": "Describe a problem and how you would solve it.",
        "comparison": "Compare two things you know well, explaining similarities and differences.",
        "instruction_follow": "Explain how to do something step by step.",
        "debate_opener": "Present an argument for or against a controversial topic."
    }
    
    return {
        "id": f"generic_{level}_{scenario_type}",
        "prompt": prompts.get(scenario_type, "Speak about any topic."),
        "context": "General practice scenario.",
        "target_structure": "General fluency practice",
        "example_opener": "Let me tell you about...",
        "vocabulary_hints": ["practice", "speak", "explain"],
        "evaluation_focus": "General accuracy and fluency",
        "scenario_type": scenario_type,
        "scenario_type_label": type_label,
        "level": level,
        "duration_seconds": duration
    }


def generate_personalization_hint(error_memory: Dict) -> str:
    """Generate a hint based on user's error memory."""
    hints = []
    
    # Check for grammar errors
    grammar_errors = error_memory.get("grammar_errors", {})
    if grammar_errors:
        top_error = max(grammar_errors.items(), key=lambda x: x[1])
        error_name = top_error[0].replace("_", " ")
        hints.append(f"Watch out for: {error_name}")
    
    # Check for missing connectors
    missing_connectors = error_memory.get("missing_connectors", [])
    if missing_connectors:
        hints.append(f"Try to use: {missing_connectors[0].replace('_', ' ')} connectors")
    
    # Check for habitual fillers
    habitual_fillers = error_memory.get("habitual_fillers", {})
    if habitual_fillers:
        top_filler = max(habitual_fillers.items(), key=lambda x: x[1])
        hints.append(f"Reduce using: '{top_filler[0]}'")
    
    return " | ".join(hints) if hints else ""


def get_all_scenario_counts() -> Dict:
    """Get counts of scenarios by level and type for coach dashboard."""
    counts = {}
    for level in LEVEL_ORDER:
        level_data = SCENARIO_LIBRARY.get(level, {})
        counts[level] = {
            "total": sum(len(scenarios) for scenarios in level_data.values()),
            "by_type": {stype: len(scenarios) for stype, scenarios in level_data.items()}
        }
    return counts


def add_custom_scenario(level: str, scenario_type: str, scenario_data: Dict) -> bool:
    """
    Add a custom scenario to the library.
    This would be called from the coach dashboard.
    """
    try:
        # Load current library
        library_path = DATA_DIR / "scenario_library.json"
        with open(library_path) as f:
            library = json.load(f)
        
        # Ensure level and type exist
        if level not in library["scenarios"]:
            library["scenarios"][level] = {}
        if scenario_type not in library["scenarios"][level]:
            library["scenarios"][level][scenario_type] = []
        
        # Generate ID if not provided
        if "id" not in scenario_data:
            existing_count = len(library["scenarios"][level][scenario_type])
            scenario_data["id"] = f"{level}_{scenario_type[:2]}_{existing_count + 1:03d}"
        
        # Add scenario
        library["scenarios"][level][scenario_type].append(scenario_data)
        
        # Save updated library
        with open(library_path, 'w') as f:
            json.dump(library, f, indent=2, ensure_ascii=False)
        
        # Reload in memory
        global SCENARIO_LIBRARY
        SCENARIO_LIBRARY = library["scenarios"]
        
        return True
    except Exception as e:
        print(f"Error adding scenario: {e}")
        return False


def get_scenario_types() -> Dict:
    """Get all scenario types with their metadata."""
    return SCENARIO_TYPES


def get_topics_by_level(level: str) -> List[str]:
    """Get suggested topics for a CEFR level."""
    topics = {
        "A1": ["Daily routines", "Family", "Food", "Hobbies", "Weather"],
        "A2": ["Past experiences", "Future plans", "Shopping", "Transportation", "Health"],
        "B1": ["Work and career", "Education", "Technology", "Environment", "Travel experiences"],
        "B2": ["Social issues", "Culture differences", "Media influence", "Economic topics"],
        "C1": ["Abstract concepts", "Philosophy", "Scientific advances", "Global politics"],
        "C2": ["Complex debates", "Nuanced arguments", "Academic discourse"]
    }
    return topics.get(level, ["General topics"])


# For testing
if __name__ == "__main__":
    # Test getting scenarios
    for level in ["A1", "A2", "B1"]:
        scenario = get_scenario(level)
        print(f"\n{level}: {scenario['prompt'][:80]}...")
    
    # Test counts
    print("\nScenario counts:")
    print(json.dumps(get_all_scenario_counts(), indent=2))
