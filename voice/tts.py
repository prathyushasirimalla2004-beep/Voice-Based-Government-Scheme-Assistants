"""
voice/tts.py — Telugu TTS for SchemeBot
Adapted from CompleteBot/voice/tts.py

Two modes:
  1. Flask API mode  → returns MP3 bytes (used by /api/tts route)
  2. Server speak mode → plays audio directly on server via pygame/playsound
"""

import os
import io
import re
import threading
import time

# ── Audio engine detection (same as CompleteBot) ─────────────────────────────
VOICE_OUT    = False
AUDIO_ENGINE = ""

try:
    from gtts import gTTS as _gTTS

    try:
        import pygame
        pygame.mixer.init()
        VOICE_OUT    = True
        AUDIO_ENGINE = "pygame"
    except Exception:
        try:
            import playsound as _playsound
            VOICE_OUT    = True
            AUDIO_ENGINE = "playsound"
        except Exception:
            # Neither pygame nor playsound — Flask-only mode still works
            VOICE_OUT    = False
            AUDIO_ENGINE = "flask_only"
except Exception:
    _gTTS = None

# Temp mp3 file path (same pattern as CompleteBot)
_AUDIO_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "_tts_output.mp3"
)

# ── English→Telugu replacements (for clean TTS) ──────────────────────────────
_REPLACEMENTS = [
    (r'\bOnline\b',              'ఆన్‌లైన్'),
    (r'\bSC\b',                  'ఎస్సీ'),
    (r'\bST\b',                  'ఎస్టీ'),
    (r'\bBC\b',                  'బీసీ'),
    (r'\bOC\b',                  'ఓసీ'),
    (r'\bMinority\b',            'మైనారిటీ'),
    (r'\bAP\b',                  'ఆంధ్రప్రదేశ్'),
    (r'\bGovt\.?\b',             'ప్రభుత్వం'),
    (r'\bgov\.in\b',             ''),
    (r'\bB\.Tech\b',             'బీటెక్'),
    (r'\bM\.Tech\b',             'ఎంటెక్'),
    (r'\bMBA\b',                 'ఎంబీయే'),
    (r'\bMCA\b',                 'ఎంసీఏ'),
    (r'\bB\.Ed\b',               'బీఎడ్'),
    (r'\bB\.Pharmacy\b',         'బీఫార్మసీ'),
    (r'\bRabi\b',                'రబీ'),
    (r'\bKharif\b',              'ఖరీఫ్'),
    (r'\bacres?\b',              'ఎకరాలు'),
    (r'\bwet\b',                 ''),
    (r'\bdry land\b',            ''),
    (r'\bland\b',                'భూమి'),
    (r'\bPahani\b',              ''),
    (r'\bWhite Ration Card\b',   'తెల్ల రేషన్ కార్డు'),
    (r'\bWhite\b',               'తెల్ల'),
    (r'\bPM[- ]?Kisan\b',        'పీఎం కిసాన్'),
    (r'\bState\b',               'రాష్ట్ర'),
    (r'\bdistrict\b',            'జిల్లా'),
    (r'\bvillage\b',             'గ్రామం'),
    (r'\bBPL\b',                 'బీపీఎల్'),
    (r'\bTC\b',                  'టీసీ'),
    (r'\(\s*\)',                  ''),   # remove empty parens
]

def clean_for_tts(text: str) -> str:
    """
    Remove English, apply replacements, keep Telugu sentences.
    Same logic as CompleteBot's speak() clean step, but smarter.
    """
    if not text: return ""

    # Remove URLs and emails
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\S+@\S+\.\S+', '', text)

    # Apply known replacements
    for pat, repl in _REPLACEMENTS:
        text = re.sub(pat, repl, text, flags=re.IGNORECASE)

    # Remove markdown formatting chars (like CompleteBot does)
    for ch in ['-', '=', '|', '+', '[', ']', '*', '#']:
        text = text.replace(ch, ' ')

    # Process sentence by sentence
    lines = text.split('.')
    kept = []
    for line in lines:
        line = line.strip()
        if not line: continue
        has_telugu = bool(re.search(r'[\u0C00-\u0C7F]', line))
        if has_telugu:
            # Strip remaining English words
            cleaned = re.sub(r'\b[a-zA-Z]{4,}\b', '', line)
            cleaned = re.sub(r'[a-zA-Z/\\+&=]+', ' ', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip(' .,/-')
            if cleaned:
                kept.append(cleaned)

    return '. '.join(kept)


def make_mp3_bytes(text: str, lang: str = "te") -> bytes | None:
    """
    Generate MP3 audio bytes using gTTS.
    Used by Flask /api/tts route — returns bytes to stream to browser.
    """
    if _gTTS is None:
        return None
    if lang == "te":
        text = clean_for_tts(text)
    text = text[:450]   # CompleteBot uses 450 char limit
    if not text or len(text) < 2:
        return None
    try:
        tts = _gTTS(text=text, lang=lang, slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        print(f"[TTS] gTTS error: {e}")
        return None


def speak(text: str, lang: str = "te"):
    """
    Speak text aloud on the SERVER using pygame or playsound.
    Runs in background thread (same pattern as CompleteBot).
    If neither pygame nor playsound available, silently skips.
    """
    if not VOICE_OUT or _gTTS is None:
        return

    def _run():
        try:
            if lang == "te":
                clean = clean_for_tts(text)
            else:
                clean = text[:450]

            if not clean or len(clean) < 2:
                return

            tts = _gTTS(text=clean[:450], lang=lang, slow=False)
            mp3 = os.path.abspath(_AUDIO_FILE)
            tts.save(mp3)

            if AUDIO_ENGINE == "pygame":
                pygame.mixer.music.load(mp3)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
            elif AUDIO_ENGINE == "playsound":
                _playsound.playsound(mp3, block=True)

        except Exception as e:
            print(f"[TTS] speak() error: {e}")

    threading.Thread(target=_run, daemon=True).start()


def is_available() -> bool:
    """Check if gTTS is importable (same as CompleteBot's is_tts_available)"""
    return _gTTS is not None
