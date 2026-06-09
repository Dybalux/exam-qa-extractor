# Tasks: Docker containerization

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

Single PR, three reviewable commits: (1) Foundation `.dockerignore` + `docker/entrypoint.sh` + `pyproject.toml`; (2) Orchestration `Dockerfile` + `docker-compose.yml` + `docker-compose.dev.yml` + `.env.example`; (3) Docs `README.md` + `README.es.md`.

## Phase 1: Foundation

- [x] 1.1 Swap `opencv-python` → `opencv-python-headless` (`>=4.8.0`) in `pyproject.toml` line 24; regen lockfile; `uv run pytest` green.
- [x] 1.2 Create `.dockerignore` (canonical list in `design.md`).
- [x] 1.3 Create `docker/entrypoint.sh` (chmod 0755): 3-state migration (fresh → `upgrade head`; unmanaged → `stamp head && upgrade head`; managed → `upgrade head`), then `exec "$@"`; `set -euo pipefail`. Verify `bash -n` clean. Depends on: 1.1

## Phase 2: Image + Orchestration

- [ ] 2.1 Create `Dockerfile` (single-stage `python:3.11-slim-bookworm`; apt install OCR+OpenCV libs + UID 1000 user + `pip install --no-cache-dir .` + `COPY --chown=app:app` entrypoint+alembic+alembic.ini+app + stdlib `HEALTHCHECK` against `/health` + uvicorn `CMD`). Depends on: 1.1, 1.2, 1.3
- [ ] 2.2 Create `docker-compose.yml` (`app` service: build → `exam-qa-extractor:latest`, `ports: ["8000:8000"]`, `env_file: [.env]`, 3 bind mounts `./data/{db,uploads,backups}` → `/app/data/*`, uvicorn `command`, `restart: unless-stopped`). Depends on: 2.1
- [ ] 2.3 Create `docker-compose.dev.yml` (override `image: exam-qa-extractor:dev`; ADD `volumes: [./app:/app/app, ./alembic:/app/alembic]` — Compose merges lists; `environment: { DEBUG: "true" }`; REPLACE `command` with uvicorn `--reload --reload-dir /app/app --reload-dir /app/alembic`). Depends on: 2.2
- [ ] 2.4 Update `.env.example`: `DATABASE_URL` → `sqlite+aiosqlite:////app/data/db/database.db` (4 slashes = absolute path); `UPLOAD_DIR=./uploads` → `UPLOAD_DIR=/app/data/uploads`; add commented `# OPENAI_API_KEY=sk-...`. Depends on: 2.2

## Phase 3: Documentation

- [ ] 3.1 Add "Run with Docker" quickstart to `README.md`: `mkdir -p data/{db,uploads,backups}` → `cp .env.example .env` + fill `OPENAI_API_KEY` + `SECRET_KEY` → `chown -R 1000:1000 ./data` if host UID ≠ 1000 → `docker compose up -d --build` → `curl /health`. Include dev-mode + rollback one-liners. Depends on: 2.2, 2.3
- [ ] 3.2 Add "Ejecutar con Docker" quickstart to `README.es.md` (Spanish translation of 3.1, matching existing tone). Depends on: 3.1

## Phase 4: Verification (manual)

- [ ] 4.1 Image: `docker build .` OK; size ≤ 600 MB; `id` → 1000; `tesseract --list-langs` has `spa`; `pip show opencv-python` not installed; `docker inspect .Config.Healthcheck` non-null
- [ ] 4.2 Runtime: `up -d` → `(healthy)`; `curl /health` 200; restart preserves bind mounts
- [ ] 4.3 Migration 3 states (fresh / unmanaged / managed) all reach running app
- [ ] 4.4 Secrets: `docker history` shows no `.env`; `docker run --rm <img> printenv OPENAI_API_KEY` exits 1
- [ ] 4.5 Dev overlay: edit `app/foo.py` → reload visible in `compose logs`; merged `compose config` keeps `data/*` + adds `app/`+`alembic/`
- [ ] 4.6 `uv run pytest` outside Docker green after headless swap
