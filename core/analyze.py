"""
core/analyze.py
Audio processing pipeline for Fluency Engine.
Shared methodology with Project 03 — Speech Fluency Analyzer.

Pipeline:
  audio bytes → save temp → transcribe (Whisper) → acoustic analysis (librosa)
  → {wpm, pauses, fillers, transcript, waveform_data, duration}
"""

import os
import re
import json
import tempfile
import numpy as np
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────────
PAUSE_THRESHOLD_DB  = 40     # top_db for librosa silence detection
PAUSE_MIN_SECONDS   = 0.40   # pauses shorter than this are ignored
SAMPLE_RATE         = 16000  # Whisper native sample rate
DATA_DIR            = Path(__file__).parent.parent / "data"

# ── Filler patterns ──────────────────────────────────────────────────────────
def _load_filler_patterns():
    with open(DATA_DIR / "filler_patterns.json") as f:
        data = json.load(f)
    return {k: re.compile(v["pattern"], re.IGNORECASE)
            for k, v in data["fillers"].items()}

FILLER_PATTERNS = _load_filler_patterns()
FILLER_META     = json.loads((DATA_DIR / "filler_patterns.json").read_text())["fillers"]


# ── Transcription ─────────────────────────────────────────────────────────────
def transcribe(audio_path: str, openai_api_key: str = None) -> str:
    """
    Transcribe audio file to text.
    Uses OpenAI Whisper API if key provided, otherwise local whisper (tiny model).
    """
    if openai_api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key)
            with open(audio_path, "rb") as af:
                result = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=af,
                    language="en"
                )
            return result.text.strip()
        except Exception as e:
            print(f"[analyze] OpenAI Whisper API failed ({e}), falling back to local.")

    # Local whisper fallback
    try:
        import whisper
        model = whisper.load_model("tiny")
        result = model.transcribe(audio_path, language="en", fp16=False)
        return result["text"].strip()
    except Exception as e:
        raise RuntimeError(f"Transcription failed: {e}. Provide an OpenAI API key or install openai-whisper.")


# ── Acoustic analysis ─────────────────────────────────────────────────────────
def _detect_pauses(y: np.ndarray, sr: int) -> list[dict]:
    """Return list of pause dicts: {start_s, end_s, duration_s}"""
    import librosa
    # Non-silent intervals
    intervals = librosa.effects.split(y, top_db=PAUSE_THRESHOLD_DB)
    pauses = []
    if len(intervals) < 2:
        return pauses
    for i in range(len(intervals) - 1):
        pause_start = intervals[i][1] / sr
        pause_end   = intervals[i + 1][0] / sr
        duration    = pause_end - pause_start
        if duration >= PAUSE_MIN_SECONDS:
            pauses.append({
                "start_s":    round(pause_start, 3),
                "end_s":      round(pause_end, 3),
                "duration_s": round(duration, 3)
            })
    return pauses


def _detect_fillers(transcript: str) -> dict:
    """
    Returns:
      total_count: int
      by_type: {filler_key: {count, label, severity}}
      instances: [str]  — for display
    """
    by_type = {}
    instances = []
    for key, pattern in FILLER_PATTERNS.items():
        matches = pattern.findall(transcript)
        if matches:
            by_type[key] = {
                "count":    len(matches),
                "label":    FILLER_META[key]["label"],
                "severity": FILLER_META[key]["severity"]
            }
            instances.extend(matches)
    return {
        "total_count": sum(v["count"] for v in by_type.values()),
        "by_type":     by_type,
        "instances":   instances
    }


def _waveform_data(y: np.ndarray, sr: int, n_points: int = 300) -> list[float]:
    """Downsample waveform to n_points for chart display."""
    chunk = max(1, len(y) // n_points)
    rms = [float(np.sqrt(np.mean(y[i:i+chunk]**2)))
           for i in range(0, len(y), chunk)][:n_points]
    max_val = max(rms) if max(rms) > 0 else 1.0
    return [round(v / max_val, 4) for v in rms]


# ── Main entry point ──────────────────────────────────────────────────────────
def analyze_audio(audio_bytes: bytes, openai_api_key: str = None) -> dict:
    """
    Full analysis pipeline.

    Args:
        audio_bytes:    Raw audio file bytes (wav, mp3, m4a, webm, ogg)
        openai_api_key: Optional — uses Whisper API if provided

    Returns dict:
        transcript:        str
        duration_s:        float
        word_count:        int
        wpm:               float
        pauses:            list[dict]
        pause_count:       int
        pause_rate:        float  (pauses per minute)
        mean_pause_dur_s:  float
        filler_data:       dict  (total_count, by_type, instances)
        filler_count:      int
        filler_rate:       float (fillers per minute)
        waveform:          list[float]  (normalized, 300 points)
        sr:                int
        error:             str | None
    """
    import librosa
    import soundfile as sf

    result = {
        "transcript": "", "duration_s": 0, "word_count": 0,
        "wpm": 0, "pauses": [], "pause_count": 0, "pause_rate": 0,
        "mean_pause_dur_s": 0, "filler_data": {}, "filler_count": 0,
        "filler_rate": 0, "waveform": [], "sr": SAMPLE_RATE, "error": None
    }

    # Save to temp file
    suffix = ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        # Load audio
        y, sr = librosa.load(tmp_path, sr=SAMPLE_RATE, mono=True)
        duration_s = librosa.get_duration(y=y, sr=sr)

        if duration_s < 3.0:
            result["error"] = "Recording too short (minimum 3 seconds)."
            return result

        result["duration_s"] = round(duration_s, 2)
        result["waveform"]   = _waveform_data(y, sr)
        result["sr"]         = sr

        # Transcription
        transcript = transcribe(tmp_path, openai_api_key)
        result["transcript"] = transcript

        # Word count & WPM
        words = [w for w in transcript.split() if w.strip()]
        word_count = len(words)
        wpm        = round((word_count / duration_s) * 60, 1) if duration_s > 0 else 0
        result["word_count"] = word_count
        result["wpm"]        = wpm

        # Pause analysis
        pauses = _detect_pauses(y, sr)
        minutes = duration_s / 60.0
        result["pauses"]           = pauses
        result["pause_count"]      = len(pauses)
        result["pause_rate"]       = round(len(pauses) / minutes, 2) if minutes > 0 else 0
        result["mean_pause_dur_s"] = round(
            sum(p["duration_s"] for p in pauses) / len(pauses), 3
        ) if pauses else 0

        # Filler analysis
        filler_data          = _detect_fillers(transcript)
        result["filler_data"]  = filler_data
        result["filler_count"] = filler_data["total_count"]
        result["filler_rate"]  = round(filler_data["total_count"] / minutes, 2) if minutes > 0 else 0

    except Exception as e:
        result["error"] = str(e)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    return result
