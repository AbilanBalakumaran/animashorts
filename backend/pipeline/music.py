"""
Sélection musicale — 100% gratuit, aucune API.
Détection de mood par mots-clés simples sur la narration.
Les pistes BGM sont des fichiers CC0 locaux dans assets/music/{mood}/
"""

import os
import random
import re
from pathlib import Path

ASSETS_DIR = Path(os.getenv("ASSETS_DIR", "./assets"))
MUSIC_DIR  = ASSETS_DIR / "music"

MOOD_DIRS = {
    "oceanic":    MUSIC_DIR / "oceanic",
    "emotional":  MUSIC_DIR / "emotional",
    "epic":       MUSIC_DIR / "epic",
    "mysterious": MUSIC_DIR / "mysterious",
    "calm":       MUSIC_DIR / "calm",
}

# Mots-clés pour détecter le mood sans IA
MOOD_KEYWORDS: dict[str, list[str]] = {
    "epic":       ["battle", "fight", "war", "power", "strong", "titan", "gear", "conquer", "army", "rage"],
    "emotional":  ["sad", "tear", "cry", "loss", "death", "sacrifice", "heart", "love", "miss", "alone", "grief"],
    "mysterious": ["secret", "mystery", "hidden", "void", "ancient", "shadow", "unknown", "dark", "forbidden"],
    "oceanic":    ["ocean", "sea", "water", "wave", "deep", "marine", "fish", "underwater", "island", "ship"],
    "calm":       ["peace", "calm", "quiet", "journey", "walk", "grow", "evolve", "begin", "story", "life"],
}

FALLBACK_MOOD = "calm"


def classify_mood_local(narration: str, hint_mood: str = "") -> str:
    """Détection de mood par comptage de mots-clés — aucune API nécessaire."""
    if hint_mood and hint_mood in MOOD_DIRS:
        return hint_mood

    text = narration.lower()
    scores = {mood: 0 for mood in MOOD_KEYWORDS}

    for mood, keywords in MOOD_KEYWORDS.items():
        for kw in keywords:
            scores[mood] += len(re.findall(r'\b' + kw + r'\b', text))

    best_mood = max(scores, key=lambda m: scores[m])
    return best_mood if scores[best_mood] > 0 else FALLBACK_MOOD


def select_track(mood: str) -> Path | None:
    mood_dir = MOOD_DIRS.get(mood, MOOD_DIRS[FALLBACK_MOOD])
    if mood_dir.exists():
        tracks = list(mood_dir.glob("*.mp3")) + list(mood_dir.glob("*.ogg"))
        if tracks:
            return random.choice(tracks)

    # Chercher dans n'importe quel dossier disponible
    for d in MOOD_DIRS.values():
        if d.exists():
            tracks = list(d.glob("*.mp3")) + list(d.glob("*.ogg"))
            if tracks:
                return random.choice(tracks)
    return None


async def get_music_for_script(narration: str, hint_mood: str = "") -> tuple[Path | None, str]:
    mood  = classify_mood_local(narration, hint_mood)
    track = select_track(mood)
    return track, mood
