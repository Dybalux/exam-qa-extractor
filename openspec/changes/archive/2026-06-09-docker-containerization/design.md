# Design: Docker containerization

## Technical Approach

Single-stage `python:3.11-slim-bookworm` with five layer groups (system
packages → Python deps → user → source → runtime). `docker/entrypoint.sh`
owns schema init (fresh → `alembic upgrade head`; unmanaged DB →
`alembic stamp head` then `upgrade head`; managed DB → `upgrade head`),
then `exec "$@"`. `docker-compose.yml` builds and bind-mounts three
data dirs; `docker-compose.dev.yml` overlays `--reload` plus live
mounts of `app/` AND `alembic/`. `pyproject.toml` swaps
`opencv-python` → `opencv-python-headless`. Secrets: `.dockerignore`
blocks `.env*`; runtime config arrives via Compose `env_file`.

## Architecture Decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Build stages | Single-stage | No C extension compiled from source; every dep has cp311 manylinux wheels. |
| 2 | Migration owner | `entrypoint.sh` (keep `lifespan.create_tables()`) | Proposal defers removing `create_tables()`. Separate job breaks single-command onboarding. |
| 3 | Entrypoint tail | `exec "$@"` | Dev overlay swaps CMD to add `--reload`; migration logic stays identical. |
| 4 | DB path detection | Hardcode `/app/data/db/database.db`; require matching `DATABASE_URL` in `.env` | Parsing `sqlite+aiosqlite:///` URLs in bash is fragile. |
| 5 | HEALTHCHECK | `python -c "import urllib.request..."` | `curl` not in `slim`; stdlib is enough. Spec allows it. |
| 6 | Dev bind mount | `./app` AND `./alembic` | New migrations live in `alembic/versions/`; without this mount they're invisible until rebuild. |
| 7 | OpenCV variant | `opencv-python-headless>=4.8.0` | Drop-in for non-GUI `cv2`. `grep` of `app/services/` shows no GUI symbols used. |
| 8 | Compose restart | `unless-stopped` | Matches `docker-compose.observability.yml` convention. |
| 9 | Dev image tag | `exam-qa-extractor:dev` | Prevents `docker compose up` (no `-f` flags) from reusing a stale dev build. |

## File Changes

| File | Action |
|------|--------|
| `Dockerfile` | Create |
| `.dockerignore` | Create |
| `docker/entrypoint.sh` | Create (mode 0755, baked into image) |
| `docker-compose.yml` | Create |
| `docker-compose.dev.yml` | Create |
| `pyproject.toml` | Modify line 24: `opencv-python` → `opencv-python-headless` |
| `.env.example` | Update `DATABASE_URL` + `UPLOAD_DIR`; add commented `OPENAI_API_KEY` |
| `README.md`, `README.es.md` | Add "Run with Docker" quickstart |
| `app/`, `alembic/`, `app/config.py`, `tests/`, `docker-compose.observability.yml` | Unchanged |

## Dockerfile

```dockerfile
FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

# Stage 1: system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-spa libmagic1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Stage 2: Python deps (cached independently of source)
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir .          # production-only; skips [dev]

# Stage 3: non-root user (UID 1000)
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid 1000 \
        --shell /bin/bash --create-home app

# Stage 4: app code + migrations
COPY --chown=app:app docker/entrypoint.sh /app/docker/entrypoint.sh
COPY --chown=app:app alembic/        /app/alembic/
COPY --chown=app:app alembic.ini     /app/alembic.ini
COPY --chown=app:app app/            /app/app/
RUN chmod +x /app/docker/entrypoint.sh

# Stage 5: runtime
USER app
EXPOSE 8000
RUN mkdir -p /app/data/db /app/data/uploads /app/data/backups \
    && chown -R app:app /app/data

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; \
    sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health',timeout=2).status==200 else 1)"

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
```

`pyproject.toml` is copied alone before `pip install` so source edits
don't bust the pip layer (spec scenario). `--chown=app:app` on COPY
avoids a post-copy `chown` that would also bust the COPY cache.
`USER app` is set AFTER apt and pip.

## docker/entrypoint.sh

```bash
#!/usr/bin/env bash
set -euo pipefail
DB_DIR="/app/data/db"
DB_FILE="${DB_DIR}/database.db"
mkdir -p "${DB_DIR}"

table_exists() {
  python - <<'PY'
import sqlite3, sys
con = sqlite3.connect("/app/data/db/database.db")
sys.exit(0 if con.execute(
  "SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'"
).fetchone() else 1)
PY
}

if [ ! -f "${DB_FILE}" ]; then
  echo "[entrypoint] No DB — fresh migrations."
  alembic upgrade head
elif table_exists; then
  echo "[entrypoint] Managed DB — applying pending."
  alembic upgrade head
else
  echo "[entrypoint] Unmanaged DB — stamping then migrating."
  alembic stamp head
  alembic upgrade head
fi

echo "[entrypoint] Launching: $*"
exec "$@"
```

`alembic` is on PATH because the image installs the project
(`alembic>=1.12.0` is a runtime dep). `alembic upgrade head` reads
`alembic.ini`, routes through `alembic/env.py` →
`app.config.get_settings()` → `DATABASE_URL` env var. `set -e` makes
migration failure abort startup. `exec "$@"` replaces the shell so
SIGTERM reaches uvicorn directly.

## docker-compose.yml

```yaml
services:
  app:
    build: { context: ., dockerfile: Dockerfile }
    image: exam-qa-extractor:latest
    container_name: exam-qa-extractor
    ports: ["8000:8000"]
    env_file: [.env]
    volumes:
      - ./data/db:/app/data/db
      - ./data/uploads:/app/data/uploads
      - ./data/backups:/app/data/backups
    command: [uvicorn, app.main:app, --host, 0.0.0.0, --port, "8000"]
    restart: unless-stopped
```

## docker-compose.dev.yml

```yaml
services:
  app:
    image: exam-qa-extractor:dev
    volumes:
      - ./app:/app/app
      - ./alembic:/app/alembic
    environment: { DEBUG: "true" }
    command: [uvicorn, app.main:app, --host, 0.0.0.0, --port, "8000",
              --reload, --reload-dir, /app/app, --reload-dir, /app/alembic]
```

Compose merges the `volumes:` lists, so the `data/` mounts from the
base file are preserved (spec: "Dev overlay does not override volumes
silently"). `command:` REPLACES the base command — intentional.

## .dockerignore

```
.env .env.* !.env.example
data/
database.db *.db *.sqlite *.sqlite3
uploads/ backup_json/ exam_images/
*.jpg *.jpeg *.png *.gif *.pdf
__pycache__/ *.py[cod]
.pytest_cache/ .mypy_cache/ .ruff_cache/ htmlcov/ .coverage
*.egg-info/ .venv/ venv/ env/ build/ dist/ *.egg
.git/ .gitignore .gitattributes
.vscode/ .idea/ .DS_Store
openspec/ .atl/
README.md README.es.md
```

## pyproject.toml change

Line 24, single edit:

```diff
-    "opencv-python>=4.8.0",
+    "opencv-python-headless>=4.8.0",
```

## Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Build | Image builds; `tesseract --list-langs` includes `spa`; `id` = 1000; `pip show opencv-python` fails; size ≤ 600 MB | Manual `docker build` + exec |
| Runtime | `docker compose up -d` → `curl localhost:8000/health` 200; `ps` shows `(healthy)` | Manual |
| Migration | 3 scenarios from spec (fresh / unmanaged / managed) | Manual: drop fixture DB, `docker compose up`, inspect schema |
| Secrets | `docker history` shows no `.env`; `docker run --rm <img> printenv OPENAI_API_KEY` exits 1 | Manual |
| Dev overlay | Edit `app/foo.py` → reload visible in `docker compose logs -f app` | Manual |
| Unit | `tests/` still passes after headless swap | `uv run pytest` outside Docker |

## Migration / Rollout

No data migration. Operator playbook (into README): `mkdir -p
data/{db,uploads,backups}` → `cp .env.example .env` and fill secrets →
`chown -R 1000:1000 ./data` if host UID ≠ 1000 → `docker compose up -d
--build` → `curl -fsS http://localhost:8000/health`. Rollback:
`docker compose down && docker rmi exam-qa-extractor:latest && git
revert`. Host bind-mounted data is untouched.

## Open Questions

None blocking. Surfacing: `docker-compose.observability.yml` is
deliberately left alone. A follow-up change could add `networks:` to
the base compose so exam-qa publishes traces to `eloise-net` /
`langfuse-net`. Out of scope here.
