# 🎙️ FLUENCY ENGINE — Improved Version
### Adaptive Spoken English Training Platform
**NO API KEYS REQUIRED — Works Completely Offline**

---

## What's New in This Version

| Feature | Original | Improved Version |
|---------|----------|------------------|
| **API Requirements** | Groq API key required | ✅ No API keys needed |
| **Scenarios** | AI-generated on-the-fly | ✅ Pre-built library (coach-editable) |
| **Corrections** | AI-powered via Groq | ✅ Rule-based pattern matching |
| **Student Accounts** | Username only | ✅ Simple login, no setup needed |
| **Coach Dashboard** | ❌ Not available | ✅ Full dashboard with insights |
| **Common Mistakes** | ❌ Not tracked across students | ✅ Class-wide analysis |
| **Areas of Opportunity** | ❌ Not identified | ✅ Automatically highlighted |

---

## What It Does

Fluency Engine is an adaptive spoken English training platform that:

1. **Presents practice scenarios** from a pre-built library organized by CEFR level (A1-C2)
2. **Records and analyzes spoken responses** using local speech processing
3. **Delivers corrective feedback** using rule-based grammar detection
4. **Tracks progress** across sessions with personalized error memory
5. **Provides coach insights** through a comprehensive dashboard

**Core loop:**
```
SCENARIO (from library, CEFR-calibrated)
        ↓
RECORD (microphone or file upload)
        ↓
ANALYSIS (Whisper + librosa — local processing)
        ↓
CORRECTIONS (rule-based pattern matching)
        ↓
SESSION LOGGED → LEVEL RECALIBRATED → NEXT SCENARIO
        ↓
REPEAT (infinite, personalised)
```

---

## Why This Version is Better for Your Use Case

### Problem with the Original
- Students needed to create Groq API accounts
- Not all students understand what an API is
- API credits can run out
- Complex setup process

### Solution in This Version
- **Zero setup for students** — just enter a username and start
- **Coach manages everything** — scenarios, monitoring, insights
- **Works offline** — no internet required for core functionality
- **Scalable** — add unlimited students without API costs

---

## CEFR Level System

| Level | Label | WPM Target | Filler Target | Connector Req. | Score |
|-------|-------|------------|---------------|----------------|-------|
| A1 | Beginner | 60–80 | ≤8/min | None | 30–40 |
| A2 | Elementary | 80–100 | ≤6/min | Sequencing | 40–52 |
| B1 | Intermediate | 100–130 | ≤4/min | + Contrast | 52–65 |
| B2 | Upper-Int. | 130–155 | ≤3/min | 3+ types | 65–76 |
| C1 | Advanced | 155–175 | ≤2/min | 4+ types | 76–88 |
| C2 | Mastery | 160–180 | ≤1.5/min | Full discourse | 88–100 |

Level progression is automatic: 3 consecutive sessions at/above threshold → advance.

---

## Technical Stack

| Layer | Tool |
|-------|------|
| Frontend | Streamlit |
| Audio recording | audio-recorder-streamlit |
| Transcription | OpenAI Whisper (local, tiny model) |
| Acoustic analysis | librosa · numpy · scipy |
| Scenario library | JSON files (editable by coach) |
| Correction engine | Rule-based pattern matching |
| Session storage | JSON files (username-keyed) |
| PDF reports | reportlab |
| Deployment | Streamlit Cloud or local |

---

## Project Structure

```
fluency-engine-improved/
├── app.py                        ← Main Streamlit app (student + coach views)
├── core/
│   ├── analyze.py                ← Audio processing: WPM, pauses, fillers
│   ├── score.py                  ← Fluency formula, connector detection
│   ├── rule_feedback.py          ← Rule-based grammar corrections (NEW)
│   ├── scenario_manager.py       ← Pre-built scenario library (NEW)
│   ├── storage.py                ← Session storage + error memory
│   ├── coach_dashboard.py        ← Coach analytics and insights (NEW)
│   └── pdf_report.py             ← PDF report generation
├── data/
│   ├── cefr_thresholds.json      ← Level boundaries and targets
│   ├── connector_taxonomy.json   ← 8 connector types with word lists
│   ├── filler_patterns.json      ← Regex patterns for filler detection
│   ├── scenario_library.json     ← Pre-built scenarios by level (NEW)
│   └── grammar_patterns.json     ← Grammar error patterns (NEW)
├── sessions/                     ← {username}_sessions.json
├── memory/                       ← {username}_memory.json
├── requirements.txt
└── README.md
```

---

## Setup Instructions

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### 2. Run the App

```bash
streamlit run app.py
```

### 3. First Time Setup

1. Open the app in your browser (usually http://localhost:8501)
2. Select **"Coach"** role
3. Enter a coach username
4. Explore the dashboard

---

## How Students Use It

1. **Open the app**
2. Select **"Student"** role
3. Enter any username (creates account automatically)
4. Select CEFR level (or let it auto-detect)
5. Click **"Get New Scenario"**
6. Record your response
7. Review analysis and corrections
8. Track progress over time

**No API keys. No setup. Just speak and learn.**

---

## How Coaches Use It

### Coach Dashboard Features

#### 📊 Overview Tab
- Total students and sessions
- Average scores and WPM
- Most active student
- Highest scoring student
- Areas of opportunity (automatically identified)

#### 👥 Students Tab
- List of all students
- Session counts and progress
- Individual student details
- Error patterns per student

#### ⚠️ Common Mistakes Tab
- Grammar errors across all students
- Missing connector types
- Common filler words
- Level distribution

#### 📈 Statistics Tab
- Score distribution histogram
- WPM vs Score scatter plot
- Progress trends

### Managing Scenarios

Edit `data/scenario_library.json` to add or modify scenarios:

```json
{
  "id": "b1_op_002",
  "prompt": "Your scenario question here?",
  "context": "Context for the student",
  "target_structure": "Grammar focus",
  "example_opener": "Suggested opening sentence",
  "vocabulary_hints": ["word1", "word2", "word3"],
  "evaluation_focus": "What to check for",
  "duration_seconds": 60
}
```

---

## Grammar Patterns Detected

The rule-based correction engine detects:

| Pattern | Example Error | Correction |
|---------|---------------|------------|
| Third person -s | He go to work | He **goes** to work |
| Past simple regular | I walk yesterday | I **walked** yesterday |
| Past simple irregular | She taked the bus | She **took** the bus |
| Present perfect | I have saw it | I have **seen** it |
| Article usage | I am student | I am **a** student |
| Plural nouns | Two book | Two **books** |
| Subject-verb agreement | They goes | They **go** |
| Prepositions | In Monday | **On** Monday |
| Comparatives | More big | **Bigger** |
| Modals | I can to swim | I **can** swim |
| Questions | You are happy? | **Are** you happy? |
| Double negatives | I don't have nothing | I don't have **anything** |

---

## Customization

### Adding New Scenarios

1. Open `data/scenario_library.json`
2. Find the appropriate CEFR level (A1-C2)
3. Find or create the scenario type
4. Add a new scenario object following the existing format

### Adding New Grammar Patterns

1. Open `data/grammar_patterns.json`
2. Add a new pattern under `"patterns"`
3. Add corresponding template under `"correction_templates"`

---

## Deployment

### Streamlit Cloud (Free)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo
4. Deploy

**Note:** On free tier, data resets on redeploy. For persistent storage:
- Use a database backend (SQLite, Supabase)
- Or export data regularly

### Local Server

```bash
streamlit run app.py --server.port 8501
```

---

## Research Foundation

Every design decision maps to established SLA (Second Language Acquisition) research:

| Design Decision | Research Basis |
|-----------------|----------------|
| Adaptive scenario difficulty | Krashen (1982) — Input Hypothesis (i+1) |
| Corrective feedback format | Long (1996) — Interaction Hypothesis |
| Explicit error marking | Schmidt (1990) — Noticing Hypothesis |
| Speaking-first practice | Swain (1985) — Output Hypothesis |
| CEFR level calibration | Council of Europe (2001) |
| Discourse connector training | Celce-Murcia et al. (2007) |
| Acoustic fluency metrics | Lennon (1990); Skehan (1996) |
| Error spaced repetition | Ebbinghaus (1885) — Forgetting Curve |

---

## Comparison: Original vs Improved

| Aspect | Original (Groq-based) | Improved (Rule-based) |
|--------|----------------------|----------------------|
| Setup complexity | High (API keys needed) | None |
| Student onboarding | Complex | Instant |
| Scenario variety | Infinite (AI-generated) | Large library (50+ scenarios) |
| Correction depth | Deep (AI understands context) | Pattern-based (18 patterns) |
| Cost | API usage costs | Free |
| Offline capability | No | Yes |
| Coach insights | Limited | Comprehensive |
| Customization | Limited | Full control |

---

## Troubleshooting

### Whisper model download fails
```bash
# Download manually
python -c "import whisper; whisper.load_model('tiny')"
```

### Audio not recording
- Check browser microphone permissions
- Try the "Upload file" tab instead

### Sessions not saving
- Ensure `sessions/` and `memory/` directories exist
- Check write permissions

---

## Future Enhancements

Possible improvements you could add:

1. **Database backend** — Replace JSON files with SQLite/PostgreSQL
2. **More grammar patterns** — Expand the rule-based engine
3. **Pronunciation feedback** — Integrate phoneme-level analysis
4. **Mobile app** — React Native wrapper
5. **Video scenarios** — Add visual context
6. **Peer review** — Students can review each other
7. **Gamification** — Points, badges, leaderboards

---

## License

MIT License — Free to use, modify, and distribute.

---

**Built for English coaches who want a simple, effective tool for their students.**

No API keys. No complexity. Just learning.
