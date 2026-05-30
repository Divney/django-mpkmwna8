# ViewMaster

Django fullscreen video viewer: log in, pick a browse order (Classic, Most Similar, Least Similar, or Favorites), and navigate ~2,236 looping `.mp4` spirals from S3 or a local folder.

## Features

- Fullscreen looping playback with swipe, arrow keys, and dial-in grid
- Order modes from bundled similarity data (full catalog only)
- **Jump to Similar** — parent + 6 nearest neighbors in a split view (full catalog only)
- Per-user favorites stored in PostgreSQL
- On-demand presigned S3 URLs (production) or local `/slideshow/` paths (offline dev)
- Discreet sign-out control; login page unchanged

## Local development

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env   # optional

uv run python manage.py migrate
uv run python manage.py createsuperuser
```

### Offline dev (no S3)

Leave `AWS_STORAGE_BUCKET_NAME` unset. Add any `.mp4` files to `viewmaster/slideshow_videos/` — the catalog is built from that folder (sorted by filename), not `videos.txt`. Similarity modes appear only when the folder count matches the full similarity datasets.

```bash
./run.sh
```

Open http://127.0.0.1:8000/

### Local dev with S3

Set bucket credentials in `.env` (see `.env.example`). Import the canonical catalog:

```bash
uv run python manage.py import_catalog
uv run python manage.py check_slideshow_storage
./run.sh
```

Videos are expected at `app/videos/{filename}` in the bucket.

## Deploy on Render

Blueprint in `render.yaml` wires Postgres and AWS env vars. `build.sh` runs `migrate` and `import_catalog`.

1. Connect repo → Apply blueprint
2. Set `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_S3_VIDEO_KEY_PREFIX=app/videos`
3. Shell: `cd viewmaster && python manage.py createsuperuser`
4. Ensure MP4s live at `s3://your-bucket/app/videos/`

## Management commands

| Command | Purpose |
|---------|---------|
| `import_catalog` | Load `homepage/data/videos.txt` into the database (production) |
| `build_top_neighbors` | Regenerate `homepage/data/top_neighbors.json` from embeddings |
| `check_slideshow_storage` | Verify catalog and S3 keys (or local folder) |

Regenerate neighbors after catalog/embeddings change:

```bash
uv run python manage.py build_top_neighbors \
  --embeddings-path ../ViewMasterApp/video_embeddings.json
```

## Data files

Bundled under `viewmaster/homepage/data/`:

- `videos.txt` — canonical catalog (imported for S3/production)
- `most_similar.json`, `least_similar.json` — browse orders
- `top_neighbors.json` — six nearest neighbors per catalog index (Jump to Similar)

## Environment variables

| Variable | Purpose |
|----------|---------|
| `AWS_STORAGE_BUCKET_NAME` | Enables S3 mode when set |
| `AWS_S3_VIDEO_KEY_PREFIX` | Default `app/videos` |
| `AWS_S3_REGION_NAME` | e.g. `us-east-1` |
| `AWS_S3_PRESIGNED_URL_EXPIRY` | Seconds (default 3600) |
| `VIEWMASTER_DEFAULT_START_INDEX` | Default `73` |
| `DATABASE_URL` | Postgres connection |

See `.env.example` for local credential patterns.
