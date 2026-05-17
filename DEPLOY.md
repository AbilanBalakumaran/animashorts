# Guide de déploiement — Accès depuis téléphone 📱

## Architecture finale

```
Ton téléphone
     │
     ▼
Vercel (frontend gratuit)
     │  /api/* et /outputs/*
     ▼
Railway (backend + worker gratuit)
     │
     ▼
Upstash Redis (gratuit)
```

**Résultat :** une URL comme `https://animashorts.vercel.app` accessible depuis n'importe quel appareil.

---

## Étape 0 — Mettre le code sur GitHub

1. Aller sur [github.com](https://github.com) → **New repository**
2. Nommer le repo `animashorts` → **Create repository**
3. Dans ton terminal Windows :

```bash
cd "C:\Users\abila\Downloads\video suki"
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/TON_USERNAME/animashorts.git
git push -u origin main
```

---

## Étape 1 — Redis gratuit avec Upstash

1. Aller sur [upstash.com](https://upstash.com) → **Sign up** (gratuit, email seulement)
2. **Create Database** → choisir une région proche (ex: EU-West)
3. Copier la **REST URL** qui ressemble à :
   ```
   rediss://default:ABCDEF...@eu1-...upstash.io:6379
   ```
4. Garder cette URL, tu en as besoin à l'étape 2.

---

## Étape 2 — Backend sur Railway

### 2a. Créer un compte Railway
1. Aller sur [railway.app](https://railway.app) → **Login with GitHub**
2. Tu as **$5 de crédit gratuit/mois** (≈ 100 vidéos)

### 2b. Déployer le backend (serveur API)
1. **New Project** → **Deploy from GitHub repo** → choisir `animashorts`
2. Railway détecte automatiquement le `railway.toml`
3. Aller dans **Variables** → ajouter :

   | Variable | Valeur |
   |----------|--------|
   | `GROQ_API_KEY` | ta clé Groq |
   | `HF_API_TOKEN` | ton token HuggingFace |
   | `REDIS_URL` | l'URL Upstash copiée à l'étape 1 |
   | `OUTPUT_DIR` | `/app/outputs` |
   | `EDGE_TTS_VOICE` | `en-US-GuyNeural` |
   | `EDGE_TTS_RATE` | `-8%` |
   | `EDGE_TTS_PITCH` | `-5Hz` |

4. Cliquer sur **Deploy** — attendre ~3 min
5. Aller dans **Settings** → **Networking** → **Generate Domain**
6. Copier l'URL générée, ex : `https://animashorts-backend-production.up.railway.app`
7. Revenir dans **Variables** → ajouter :

   | Variable | Valeur |
   |----------|--------|
   | `PUBLIC_API_URL` | l'URL copiée ci-dessus |

### 2c. Déployer le worker Celery (séparé)
1. Dans Railway, **New Service** → **GitHub repo** → `animashorts`
2. Aller dans **Settings** → **Deploy** → **Start Command** :
   ```
   celery -A workers.celery_app worker --loglevel=info --concurrency=1 -Q video_pipeline
   ```
3. Ajouter les **mêmes variables** que pour le backend (étape 2b)
4. **Deploy**

---

## Étape 3 — Frontend sur Vercel

### 3a. Créer un compte Vercel
1. Aller sur [vercel.com](https://vercel.com) → **Sign up with GitHub**

### 3b. Mettre à jour vercel.json avec ton URL Railway

Dans le fichier `frontend/vercel.json`, remplacer `REMPLACER_PAR_URL_RAILWAY` par ton URL Railway :

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://animashorts-backend-production.up.railway.app/api/:path*"
    },
    {
      "source": "/outputs/:path*",
      "destination": "https://animashorts-backend-production.up.railway.app/outputs/:path*"
    }
  ]
}
```

Puis pousser sur GitHub :
```bash
git add frontend/vercel.json
git commit -m "Set Railway URL in vercel.json"
git push
```

### 3c. Déployer sur Vercel
1. **New Project** → importer le repo `animashorts`
2. **Root Directory** → choisir `frontend`
3. **Framework Preset** → Next.js (détecté automatiquement)
4. Aucune variable d'environnement nécessaire (les rewrites gèrent tout)
5. **Deploy** — ~2 minutes

### 3d. Récupérer ton URL publique
Vercel génère une URL du type :
```
https://animashorts.vercel.app
```

**C'est cette URL que tu ouvres sur ton téléphone. ✅**

---

## Résumé des URLs

| Service | URL |
|---------|-----|
| **Ton site (téléphone)** | `https://animashorts.vercel.app` |
| Backend API | `https://animashorts-backend.up.railway.app` |
| Redis | Upstash (interne) |

---

## Vérifier que tout fonctionne

1. Ouvrir `https://animashorts.vercel.app` sur ton téléphone
2. Entrer un prompt : *"Jinbe's design evolution in One Piece. Oceanic atmosphere."*
3. Choisir **16s** → cliquer **Generate**
4. La barre de progression s'affiche → attendre ~2-3 min
5. La vidéo apparaît, tu peux la télécharger directement sur ton téléphone

---

## Coûts réels

| Service | Coût |
|---------|------|
| Vercel (frontend) | **Gratuit pour toujours** |
| Railway (backend) | **Gratuit** ($5 crédit/mois ≈ 100 vidéos) |
| Upstash (Redis) | **Gratuit** (10 000 cmd/jour) |
| Groq (LLM) | **Gratuit** (14 400 req/jour) |
| HuggingFace (images) | **Gratuit** (rate limité) |
| edge-tts (voix) | **Gratuit pour toujours** |
| **Total** | **0 €/mois** |

---

## Problèmes fréquents

**"La génération échoue avec une erreur d'image"**
→ HuggingFace est rate-limité. Attendre 1 minute et réessayer, ou vérifier que `HF_API_TOKEN` est bien défini.

**"Le worker ne démarre pas sur Railway"**
→ Vérifier que toutes les variables d'environnement sont copiées dans le service worker aussi.

**"Les vidéos disparaissent après redéploiement"**
→ Normal avec Railway (stockage éphémère). Pour conserver les vidéos, ajouter un volume Railway ($0.25/Go/mois) ou Cloudflare R2.

**"L'URL Railway dans vercel.json n'est pas la bonne"**
→ Aller dans Railway → ton service → **Settings** → **Domains** pour retrouver l'URL exacte.
