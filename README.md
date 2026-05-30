# ViewMaster

Django slideshow app: log in, then browse looping `.mp4` videos from a local folder or S3.

## Local development

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/) (or use `pip` with `requirements.txt`).

```bash
uv sync

# Optional: point at Postgres instead of the default local URL in settings.py
# export DATABASE_URL='postgresql://postgres:postgres@localhost:5432/viewmaster'

uv run python manage.py migrate
uv run python manage.py createsuperuser
```

### Videos: local folder (default)

Add `.mp4` files under `viewmaster/slideshow_videos/`. No AWS setup required.

### Videos: test against S3 locally

The app uses S3 when `AWS_STORAGE_BUCKET_NAME` is set; otherwise it reads the local folder. Credentials are loaded the same way as on Render (environment variables), with a repo-root `.env` file for convenience.

1. Copy the template and edit it:

   ```bash
   cp .env.example .env
   ```

2. Put `.env` in the **repo root** (next to `run.sh` and `manage.py`). It is gitignored.

3. Set at least the bucket name and region. For credentials, pick **one** approach:

   **Option A — keys in `.env`** (simple; use a dev-only IAM user):

   ```env
   AWS_STORAGE_BUCKET_NAME=your-bucket-name
   AWS_S3_REGION_NAME=us-east-1
   AWS_S3_SLIDESHOW_PREFIX=slideshow/
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   ```

   **Option B — AWS CLI profile** (keeps secrets out of the project; recommended if you already use `aws configure`):

   ```env
   AWS_STORAGE_BUCKET_NAME=your-bucket-name
   AWS_S3_REGION_NAME=us-east-1
   AWS_PROFILE=viewmaster-dev
   ```

   With option B, store keys in `~/.aws/credentials` under `[viewmaster-dev]` via `aws configure --profile viewmaster-dev`.

4. Upload test videos (separate uploader credentials are fine):

   ```bash
   aws s3 sync ./viewmaster/slideshow_videos/ s3://your-bucket-name/slideshow/
   ```

5. Verify connectivity without starting the server:

   ```bash
   uv run python manage.py check_slideshow_storage
   ```

6. Run the app as usual — `./run.sh` loads `.env` automatically via Django settings.

To switch back to local files, remove or comment out `AWS_STORAGE_BUCKET_NAME` in `.env`.

Run the server:

```bash
./run.sh
```

Open http://127.0.0.1:8000/ — you will be redirected to login, then the slideshow.

## Deploy on Render

This repo includes a [Render Blueprint](https://render.com/docs/infrastructure-as-code) (`render.yaml`) that creates a web service and PostgreSQL database. `DATABASE_URL` is wired automatically.

1. Push this directory as its own Git repo (so `render.yaml` is at the repo root), or set **Root Directory** to `viewmaster-django` if it lives in a monorepo.
2. In the [Render Dashboard](https://dashboard.render.com) → **Blueprints** → **New Blueprint Instance** → connect the repo → **Apply**.
3. After the first deploy succeeds, open the web service **Shell** and create an admin user:

   ```bash
   cd viewmaster && python manage.py createsuperuser
   ```

4. In the web service **Environment**, set the AWS variables (see `.env.example`): `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and optionally `AWS_S3_SLIDESHOW_PREFIX`. Upload `.mp4` files with `aws s3 sync` from your machine.

Manual setup (without Blueprint) is described in [Deploy a Django App on Render](https://render.com/docs/deploy-django). Use:

- **Build command:** `./build.sh`
- **Start command:** `python -m gunicorn viewmaster.wsgi:application --chdir viewmaster --bind 0.0.0.0:$PORT`
- **Environment:** `DATABASE_URL` (internal Postgres URL), `SECRET_KEY` (generate), optional `WEB_CONCURRENCY=4`

On Render, `DEBUG` is off, static files are served via WhiteNoise, and migrations run during each deploy in `build.sh`.

### `ModuleNotFoundError: No module named 'mysite'`

Render is still using the old Django template start command (`mysite.asgi` + Uvicorn). This project uses WSGI at `viewmaster.wsgi`. In the web service **Settings**, set **Start Command** to the command above (or sync your Blueprint from `render.yaml`). Remove any `mysite.asgi` / `uvicorn.workers` command.
