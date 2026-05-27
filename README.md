# ViewMaster

Django slideshow app: log in, then browse images from `viewmaster/slideshow_images/`.

## Local development

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/) (or use `pip` with `requirements.txt`).

```bash
uv sync

# Optional: point at Postgres instead of the default local URL in settings.py
# export DATABASE_URL='postgresql://postgres:postgres@localhost:5432/viewmaster'

uv run python manage.py migrate
uv run python manage.py createsuperuser
```

Add images under `viewmaster/slideshow_images/` (`.jpg`, `.png`, `.gif`, `.webp`).

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

4. Upload slideshow images to `viewmaster/slideshow_images/` on the instance (or add persistent storage later). Images are not in git by default (see `.gitignore`).

Manual setup (without Blueprint) is described in [Deploy a Django App on Render](https://render.com/docs/deploy-django). Use:

- **Build command:** `./build.sh`
- **Start command:** `cd viewmaster && python -m gunicorn viewmaster.wsgi:application --bind 0.0.0.0:$PORT`
- **Environment:** `DATABASE_URL` (internal Postgres URL), `SECRET_KEY` (generate), optional `WEB_CONCURRENCY=4`

On Render, `DEBUG` is off, static files are served via WhiteNoise, and migrations run during each deploy in `build.sh`.
