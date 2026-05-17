# AnimaShorts AI 🎌

> Transforme n'importe quelle idée anime en un short TikTok/YouTube Shorts entièrement monté — **100% gratuit**.

**AnimaShorts AI** est un générateur de vidéos verticales (1080×1920) spécialisé anime.
Un prompt → un MP4 avec narration IA, visuels anime, effets cinématiques et musique.

---

## Stack 100% Gratuit

| Composant | Service | Coût | Compte requis |
|-----------|---------|------|---------------|
| Script IA | **Groq** (Llama 3.3 70B) | Gratuit | Email seulement |
| Voix | **edge-tts** (Microsoft Edge Neural) | Gratuit | Aucun |
| Images | **HuggingFace Inference API** | Gratuit | Email seulement |
| Timestamps | **faster-whisper** (local) | Gratuit | Aucun |
| Musique | Fichiers CC0 locaux | Gratuit | Aucun |
| Vidéo | **MoviePy + FFmpeg** | Gratuit | Aucun |

**Coût total par vidéo : 0 €**

---

## Démarrage rapide

### 1. Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installé
- 2 comptes gratuits (5 minutes) :
  - [Groq](https://console.groq.com) → récupérer une clé API gratuite
  - [HuggingFace](https://huggingface.co/settings/tokens) → créer un token (Read)

### 2. Cloner et configurer

```bash
git clone https://github.com/youruser/animashorts.git
cd animashorts
cp .env.example .env
```

Éditer `.env` et remplir uniquement :

```env
GROQ_API_KEY=gsk_...        # collé depuis console.groq.com
HF_API_TOKEN=hf_...         # collé depuis huggingface.co/settings/tokens
```

C'est tout. Aucune autre clé nécessaire.

### 3. Ajouter de la musique (optionnel mais recommandé)

Placer des fichiers `.mp3` CC0 dans `backend/assets/music/` par mood :

```
backend/assets/music/
├── calm/
├── emotional/
├── epic/
├── mysterious/
└── oceanic/
```

Sources gratuites : [Pixabay Music](https://pixabay.com/music/) · [Free Music Archive](https://freemusicarchive.org) · [Incompetech](https://incompetech.com)

### 4. Lancer

```bash
docker compose up --build
```

Ouvrir **http://localhost:3000** — c'est prêt.

---

## Pipeline

```
Prompt utilisateur
      ↓
Groq Llama 3.3 70B  →  script + 4 prompts visuels (JSON)
      ↓
edge-tts (Microsoft)  →  narration MP3 (voix neurale documentaire)
      ↓
HuggingFace Inference  →  4 images anime 768×1344 en parallèle
      ↓
faster-whisper (local)  →  timestamps par mot (si sous-titres)
      ↓
MoviePy  →  effet Ken Burns + transitions crossfade
      ↓
FFmpeg  →  mixage BGM 12% volume + burn sous-titres optionnel
      ↓
final_short.mp4  (1080×1920, H.264, ~8 Mo)
```

---

## Installation manuelle (sans Docker)

### Système requis

- Python 3.11+
- Node.js 20+
- FFmpeg (`ffmpeg -version`)
- Redis

```bash
# ── Backend ──────────────────────────────────────────
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

# Terminal 1 — Serveur API
uvicorn main:app --reload --port 8000

# Terminal 2 — Worker Celery
celery -A workers.celery_app worker --loglevel=info -Q video_pipeline

# ── Frontend ──────────────────────────────────────────
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Ouvrir **http://localhost:3000**

---

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `GROQ_API_KEY` | — | **Obligatoire.** Clé Groq gratuite |
| `HF_API_TOKEN` | *(vide)* | Token HuggingFace (recommandé, gratuit) |
| `EDGE_TTS_VOICE` | `en-US-GuyNeural` | Voix Microsoft Edge |
| `EDGE_TTS_RATE` | `-8%` | Vitesse de parole |
| `EDGE_TTS_PITCH` | `-5Hz` | Tonalité de voix |
| `REDIS_URL` | `redis://redis:6379/0` | URL Redis |
| `OUTPUT_DIR` | `./outputs` | Répertoire de sortie vidéos |
| `VIDEO_WIDTH` | `1080` | Largeur vidéo |
| `VIDEO_HEIGHT` | `1920` | Hauteur vidéo |
| `VIDEO_FPS` | `30` | Images par seconde |

---

## Architecture

```
Navigateur
  └── Next.js 14 (port 3000)
        └── /api/* → FastAPI (port 8000)
                └── Celery Worker
                      ├── script_gen.py   → Groq Llama 3.3 70B (gratuit)
                      ├── tts.py          → edge-tts Microsoft (gratuit, sans compte)
                      ├── image_gen.py    → HuggingFace Inference (gratuit)
                      ├── music.py        → détection mots-clés + CC0 local (gratuit)
                      ├── video_editor.py → MoviePy + FFmpeg (gratuit)
                      └── subtitle.py     → faster-whisper local (gratuit)
Redis (queue + statut des jobs)
outputs/{job_id}/
  ├── narration.mp3
  ├── scene_01.png ... scene_N.png
  ├── subtitles.srt  (si activé)
  └── final_short.mp4
```

---

## Fonctionnalités

| Fonctionnalité | Détails |
|---|---|
| **Format** | 9:16 vertical, 1080×1920, H.264 MP4 |
| **Durées** | 16s / 30s / 60s |
| **Voix** | Microsoft Edge Neural (en-US-GuyNeural par défaut) |
| **Visuels** | Modèles anime HuggingFace (Animagine XL 3.1) |
| **Script** | Groq Llama 3.3 70B |
| **Effets** | Ken Burns zoom+pan, transitions crossfade |
| **Musique** | Mood détecté par mots-clés + piste CC0 locale |
| **Sous-titres** | faster-whisper local, synchronisé par mot |
| **Styles** | Oceanic · Emotional · Epic · Mysterious · Documentary |
| **Queue** | Celery + Redis — jobs concurrents |

---

## Limites des services gratuits

| Service | Limite gratuite |
|---------|----------------|
| Groq | 30 req/min · 14 400 req/jour · 6 000 tokens/min |
| HuggingFace Inference | ~5 req/min sans token, ~10-20 req/min avec token |
| edge-tts | Illimité (serveurs Microsoft Edge) |
| faster-whisper | Illimité (local CPU) |

Pour un usage intensif, Groq propose des plans payants à partir de $0.05/M tokens (environ 1000× moins cher que GPT-4).

---

## Déploiement GitHub

### GitHub Actions (inclus)

`.github/workflows/deploy.yml` construit les images Docker et déploie par SSH sur push vers `main`.

**Secrets GitHub requis :**
- `VPS_HOST` — IP ou domaine du serveur
- `VPS_USER` — nom d'utilisateur SSH
- `VPS_SSH_KEY` — clé SSH privée

### VPS recommandé

2 cœurs, 4 Go RAM, 30 Go SSD suffisent (ex: Hetzner CX22 ~4€/mois).

```bash
# Sur le VPS :
sudo apt install -y docker.io docker-compose-plugin
mkdir ~/animashorts && cd ~/animashorts
# Uploader votre .env
docker compose up -d
```

---

## Roadmap MVP

- [x] Pipeline complet (script → TTS → images → rendu)
- [x] Effets Ken Burns + transitions crossfade
- [x] Musique auto par mood (local CC0)
- [x] Sous-titres optionnels (faster-whisper)
- [x] Queue Celery + Redis
- [x] Docker Compose
- [x] Frontend Next.js avec suivi de progression
- [ ] Galerie avec aperçu au survol
- [ ] Sélecteur de voix edge-tts dans l'UI
- [ ] Ratio 1:1 et 4:5
- [ ] Diffusion locale avec ComfyUI (qualité supérieure)
- [ ] Génération par lot

---

## Tech Stack

| Couche | Technologie |
|--------|-------------|
| Frontend | Next.js 14, TailwindCSS, Framer Motion |
| Backend | Python 3.11, FastAPI, Pydantic v2 |
| Queue | Celery 5, Redis 7 |
| Script IA | Groq (Llama 3.3 70B) — **gratuit** |
| Voix | edge-tts (Microsoft Edge) — **gratuit** |
| Images | HuggingFace Inference (Animagine XL 3.1) — **gratuit** |
| Timestamps | faster-whisper (local) — **gratuit** |
| Vidéo | MoviePy, FFmpeg — **gratuit** |
| Conteneurs | Docker, Docker Compose |
| CI/CD | GitHub Actions → SSH deploy |

---

## Licence

MIT — libre d'utilisation, modification et déploiement commercial.
