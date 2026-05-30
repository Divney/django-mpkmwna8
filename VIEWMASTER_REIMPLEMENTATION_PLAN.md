# ViewMaster Django Reimplementation Plan

**Status:** Approved decisions recorded — **no code changes until you say “go ahead”.**

**Goal:** Port all user-facing features from the static S3-hosted app (`/Users/dsaunder/ViewMasterApp`) into the Django app (`viewmaster-django`), while **keeping the existing Django login page** and **S3-backed video access**. Replace browser-only state (especially favorites) with **Django-native, database-backed** behavior.

---

## Decisions (locked in)

| # | Topic | Decision |
|---|--------|----------|
| Q1 | S3 bucket layout | **`app/videos/{filename}`** — matches static app. Set `Video.s3_key` (or env prefix) accordingly; use existing `viewmaster` bucket. |
| Q2 | Catalog source | **`videos.txt` is canonical** for production/S3. Bundle in Django repo: `homepage/data/videos.txt`, `most_similar.json`, `least_similar.json`. Import into Postgres via management command. |
| Q3 | Similarity orders | **Option A** — JSON files in repo; serve to client (static files or thin read-only view). No DB tables for orders. |
| Q4 | Favorites | **Per-user** (`Favorite` per `auth.User`). No admin view/export for now. |
| Q5 | Sign out in viewer | **Option B** — small discreet control (low opacity), not a full header bar. |
| Q6 | Video URLs | **On-demand API** — presigned URL per video when needed; prefetch neighbors optional. Refresh on playback error / before expiry for long sessions. |
| Q7 | Default start | **Catalog index 73** (0-based), same as static app (`0073classicspiral.mp4`). |
| Q8 | Quirks | **Fix** Escape so it exits real fullscreen (and syncs icon). **Fix** grid-open so swipe does not navigate. **Keep** videos muted (autoplay-friendly). |
| Q9 | Fullscreen icons | **Copy PNGs** from `ViewMasterApp/app/img/` → `homepage/static/homepage/img/`. |
| Q10 | Local dev without S3 | **Do not use `videos.txt`.** Build catalog from **whatever `.mp4` files exist** in `viewmaster/slideshow_videos/` (sorted by filename). Same viewer UI; local URLs via existing DEBUG media serve or equivalent API path. |

---

## 1. Source app — feature inventory

The static app (`index.html` + `app/js/app.js`) is a fullscreen looping MP4 viewer for **~2,236 videos**.

### Playback & layout

- Single fullscreen `<video>`: autoplay, loop, **muted**, `object-fit: contain`, black background
- No prev/next buttons in the main UI (navigation is keyboard / swipe / dial-in only)
- Fullscreen toggle button (bottom-right), icon swaps expand ↔ compress (PNG assets)

### Startup — order selection overlay

On load, after data is fetched:

1. Shows catalog video at **index 73** (`0073classicspiral.mp4` in `videos.txt`)
2. Semi-transparent overlay with frosted-glass buttons:
   - **Classic** — order from `videos.txt`
   - **Most Similar** — order from `most_similar.json` (CLIP embedding walk)
   - **Least Similar** — order from `least_similar.json`
   - **Favorites (N)** — only if user has favorites

Overlay blocks navigation until a mode is chosen.

### Navigation

| Input | Action |
|-------|--------|
| ← / → | Previous / next in current order (wraps) |
| Swipe left (≥50px) | Next |
| Swipe right (≥50px) | Previous |
| Click/tap background | Show 3×4 numeric grid (auto-hides after 3s) |
| Grid digits 0–9 | Buffer → jump to **1-indexed catalog number** after 1s debounce |
| **Rand** | Random catalog video; switches to Classic if needed |
| **Favs** | Switch to favorites mode at first favorite (disabled if empty) |

**Improvement vs static:** while grid is open, swipe/arrow navigation does not fire.

### Index display (top-left)

- Shows `{catalogNumber} of {total}` (1-indexed)
- Fades out after ~2s
- During grid typing: shows raw digit buffer (invalid numbers flash red)

### Favorites (top-right ★)

| Input | Action |
|-------|--------|
| Click ★ | Toggle favorite |
| Spacebar | Toggle favorite |

- **Django:** persisted per user in Postgres (replaces `localStorage`)
- Gold star when favorited; favorites mode rebuilds order on unfavorite; empty favorites → back to order selection on video 73

### Data files

| File | Purpose |
|------|---------|
| `homepage/data/videos.txt` | Canonical catalog (production import) |
| `homepage/data/most_similar.json` | Catalog index order — nearest-neighbor walk |
| `homepage/data/least_similar.json` | Catalog index order — furthest-neighbor walk |
| S3 `app/videos/*.mp4` | Video blobs (production) |
| Local `viewmaster/slideshow_videos/*.mp4` | Offline dev only — catalog = folder contents |

### Not in scope

Ratings, tags, thumbnails, text search, embedding-space UI, pause/speed/brightness controls, autoplay-through-order mode, favorites admin/export.

---

## 2. Current Django app — what we keep

| Keep as-is | Notes |
|------------|-------|
| **Login page** (`homepage/templates/homepage/login.html`) | Username/password, current styling |
| **Auth flow** | `LoginView`, `@login_required` on viewer + APIs, POST logout |
| **S3 access** | `boto3` presigned GET via env vars (`.env` locally, Render in prod) |
| **Deploy stack** | Render, Postgres, WhiteNoise, Gunicorn |

| Replace / remove | Notes |
|------------------|-------|
| Minimal slideshow template | Prev/next bar — not in static app |
| Flat S3 list as catalog | Replaced by `videos.txt` import (prod) or folder scan (local) |
| `localStorage` favorites | Replaced by DB + API |

---

## 3. Architecture (Django-native)

### 3.1 Catalog

**Production / S3 mode** (`AWS_STORAGE_BUCKET_NAME` set):

- Import `homepage/data/videos.txt` → `Video` rows
- Each row: `catalog_index` (0-based line number), `filename`, `s3_key` = `app/videos/{filename}`
- Management command: `import_catalog` (re-runnable for sync)

**Local offline mode** (no bucket name):

- **Skip `videos.txt`**
- Scan `viewmaster/slideshow_videos/` for `*.mp4`, sort by filename
- Assign `catalog_index` 0…n−1 in that sort order
- `s3_key` unused; playback via `/slideshow/{filename}` (DEBUG media) or local URL API

**Note:** Similarity JSON arrays reference the **full** ~2,236-index catalog. In local folder-only mode with a subset of files, similarity modes may reference missing indices — handle gracefully (skip missing / fall back to classic only) or document that full similarity requires production catalog import.

```
Video
  - id (PK)
  - catalog_index (unique per deployment catalog)
  - filename
  - s3_key (e.g. "app/videos/0073classicspiral.mp4"; blank in pure local mode if desired)
```

### 3.2 Similarity orders (Option A)

- Files live in repo: `homepage/data/most_similar.json`, `least_similar.json`
- Served to authenticated client on slideshow load (template `json_script` or static URL under `/static/`)
- **No** `import_similarity_orders` command or order tables

### 3.3 Favorites

```
Favorite
  - user (FK → auth.User)
  - video (FK → Video)
  - created_at
  - unique_together (user, video)
```

- `GET /api/favorites/` → list of user's `catalog_index` values
- `POST /api/favorites/toggle/` → `{ "catalog_index": 73 }` → `{ "favorited": true/false }`
- Bootstrap: include favorite indices in initial page context or first API call

### 3.4 Video URLs (on-demand API)

1. **Page load:** catalog size, filenames/indices, similarity arrays, user favorites, `default_start_index: 73`, mode flags
2. **Playback:** `GET /api/videos/<catalog_index>/url/`
   - **S3:** returns fresh presigned URL for `Video.s3_key`
   - **Local:** returns `/slideshow/{filename}` or equivalent
3. **Prefetch:** optional next/prev URL fetch in JS
4. **Long sessions:** on `video` `error` or stalled load, re-request URL for current index

### 3.5 Viewer UI

- Port layout/CSS/behavior from static `index.html` + `app.js` → `slideshow.html` + `homepage/static/homepage/viewer.js` (+ CSS if split)
- Copy PNGs: `arrows-alt_ffffff_64.png`, `compress_ffffff_64.png`
- **No** prev/next footer bar
- **Discreet sign-out** — small low-opacity control (e.g. corner), POST to logout with CSRF
- **Fullscreen:** `Escape` exits browser fullscreen and resets icon (fixed behavior)
- **Grid:** when visible, block arrow/swipe navigation

### 3.6 URL routes

| Route | Purpose |
|-------|---------|
| `/` | Redirect → slideshow or login |
| `/login/`, `/logout/` | Unchanged |
| `/slideshow/` | Fullscreen viewer (login required) |
| `/api/videos/<int:catalog_index>/url/` | Playback URL (presigned or local) |
| `/api/favorites/` | GET user's favorite catalog indices |
| `/api/favorites/toggle/` | POST toggle favorite |

### 3.7 Management commands

| Command | Purpose |
|---------|---------|
| `import_catalog` | Load `homepage/data/videos.txt` → `Video`; `s3_key` = `app/videos/{filename}` |
| `check_slideshow_storage` | Verify S3 objects exist for catalog keys; local mode reports folder count |

**Removed from plan:** `import_similarity_orders` (Option B).

### 3.8 S3 configuration

- **Prefix / keys:** `app/videos/{filename}`
- **Env:** set `AWS_S3_SLIDESHOW_PREFIX=app/videos/` (or derive `s3_key` on model only and list by catalog)
- **Bucket:** existing `viewmaster` bucket (name via `AWS_STORAGE_BUCKET_NAME`)
- **Source data to copy into repo once:** from `ViewMasterApp/app/` → `homepage/data/`

---

## 4. Implementation phases

### Phase 1 — Data layer

1. Add `Video` and `Favorite` models + migrations
2. Add `homepage/data/` with `videos.txt`, `most_similar.json`, `least_similar.json`
3. `import_catalog` from bundled `videos.txt`
4. Catalog builder for local folder-only mode (no `videos.txt`)
5. Extend `check_slideshow_storage` for catalog ↔ S3 cross-check

### Phase 2 — API layer

1. `GET /api/videos/<catalog_index>/url/` (login required; S3 presign or local path)
2. Favorites GET + toggle
3. Tests: auth, toggle, URL generation

### Phase 3 — Viewer UI

1. Template + `viewer.js` + CSS port from static app
2. Favorites via API (not `localStorage`)
3. On-demand URL loading + optional prefetch
4. Order overlay, grid, swipe, keyboard, star, fullscreen PNGs
5. **Fixes:** Escape ↔ fullscreen; no nav while grid open; muted video

### Phase 4 — Polish & deploy

1. README + `.env.example` (`AWS_S3_SLIDESHOW_PREFIX=app/videos/`)
2. URL refresh on playback failure
3. QA checklist (below)
4. Document local-dev vs production catalog behavior

---

## 5. QA checklist (acceptance criteria)

- [ ] Login page unchanged in look and behavior
- [ ] Viewer matches static layout (no old prev/next bar)
- [ ] Discreet sign-out control works
- [ ] Order selection: Classic / Most Similar / Least Similar / Favorites (N)
- [ ] Starts on catalog index **73** with overlay
- [ ] Arrow keys and swipe navigate (not while grid is open)
- [ ] Click background → grid, 3s auto-hide, dial-in, Rand, Favs
- [ ] Index label `N of {total}` with fade
- [ ] ★ and Space toggle favorite; persists per user across sessions
- [ ] Favorites mode + empty favorites → order selection on 73
- [ ] Fullscreen button works; **Escape exits fullscreen** and icon matches state
- [ ] Videos muted, loop, autoplay
- [ ] Production: S3 `app/videos/` via presigned on-demand API
- [ ] Local (no S3): plays files from `slideshow_videos/` without `videos.txt`

---

## 6. Files expected to change (when implementation starts)

| Area | Files |
|------|-------|
| Models | `homepage/models.py`, migrations |
| Data | `homepage/data/videos.txt`, `most_similar.json`, `least_similar.json` |
| API | `homepage/views.py` (and/or `api.py`), `homepage/urls.py` |
| Storage | `homepage/slideshow_sources.py` — presign by `s3_key`, local path helper |
| Viewer | `homepage/templates/homepage/slideshow.html`, `static/homepage/viewer.js`, `viewer.css` |
| Commands | `import_catalog`, updated `check_slideshow_storage` |
| Config | `settings.py`, `.env.example`, `README.md` |
| Assets | `static/homepage/img/*.png` (copied from ViewMasterApp) |

**Not changing:** `login.html`, Render blueprint structure (except env docs for `app/videos/` prefix).

---

## 7. Estimated effort

| Phase | Rough size |
|-------|------------|
| Phase 1 — Models + import + local catalog | Small–medium |
| Phase 2 — API | Small |
| Phase 3 — UI port + fixes | Medium |
| Phase 4 — Docs + QA | Small |

---

## 8. Next step

Reply **“go ahead”** when you want implementation to begin. Until then, no application code changes.
