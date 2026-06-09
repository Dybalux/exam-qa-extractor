# Exploration: Docker containerization for exam-qa-extractor

**Change slug:** `docker-containerization`
**Date:** 2026-06-08
**Mode:** engram + openspec (hybrid artifact)
**Verdict:** Ready for proposal. All topics investigated, recommendations grounded in code + verified ecosystem facts.

---

## Current State

The app is a **FastAPI + SQLite** service with OCR (pytesseract + opencv-python) and OpenAI Vision integration. It reads config from `.env` via pydantic-settings, mounts static files, and runs a `lifespan` hook that calls `create_tables()` (SQLAlchemy `metadata.create_all`) on startup.

**Confirmed from code:**

- `app/main.py:25-29` — `lifespan` calls `await create_tables()`. **No `alembic upgrade head` is run automatically.**
- `app/db/init_db.py:13-17` — `create_tables()` uses `Base.metadata.create_all` (idempotent, but does NOT run migrations).
- `alembic/versions/` — 3 migrations exist (`001_initial`, `002_remove_difficulty`, `003_add_uuid_columns`). They use **hardcoded revision IDs as strings** (`revision = '001_initial'`, `down_revision = None`) — this is non-standard (Alembic normally uses 12-char hex hashes) and `alembic upgrade head` will still work because `env.py` is wired correctly.
- `app/config.py:13-16` — Settings read `.env` from CWD via `pydantic-settings`. If the file is not present, defaults are used (no hard crash).
- `docker-compose.observability.yml` — Already exists for Langfuse/Prometheus/Grafana/Jaeger. The app itself is **not** in any container.
- `.gitignore` — `.env`, `*.db`, `uploads/`, `backup_json/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.coverage`, `*.egg-info/` are all already ignored. This is a **good starting point for `.dockerignore`** (copy with adjustments).
- `app/api/v1/endpoints/` is currently empty (only `__pycache__/`). Wiring happens in `app/api/__init__.py` via direct module imports. Non-issue for Docker but worth noting.
- **`.env` contains a real `OPENAI_API_KEY`** and several Langfuse secrets. These MUST NOT end up in any image layer.

**System deps for runtime (per `pyproject.toml` + `README`):**

- `tesseract-ocr`, `tesseract-ocr-spa` (Spanish lang data)
- `libmagic1` (for `python-magic`)
- `libgl1-mesa-glx` (or `libgl1` on newer Debian), `libglib2.0-0` (opencv-python runtime)

**Pyproject deps (relevant to base image choice):**

- `opencv-python>=4.8.0` — ships pre-built `manylinux2014` wheels for cp37-cp314. **No compilation needed on any glibc distro.** PyPI's own docs explicitly recommend `opencv-python-headless` for Docker (smaller, no Qt). For this project, **swap to `opencv-python-headless`** since the app does no `cv2.imshow` (only image processing + tesseract handoff).
- `pymupdf>=1.23.0` — also has pre-built wheels; works on slim.
- `pytesseract`, `pillow`, `numpy` — pure Python or wheels, no build deps.

---

## Affected Areas

- `Dockerfile` (new) — image definition.
- `docker-compose.yml` (new) — local dev stack (the app + volumes). The existing `docker-compose.observability.yml` stays untouched and is brought up separately.
- `.dockerignore` (new) — keep build context small and prevent secret leaks.
- `app/config.py` — **no change required**; already env-var driven.
- `app/main.py` — **no change required**; `lifespan` already creates tables for first-run.
- `README.md` / `README.es.md` — add Docker quickstart section (user has already asked for an architecture diagram too, post-Docker).
- `pyproject.toml` — consider swapping `opencv-python` → `opencv-python-headless` to save ~50-100 MB. Optional but recommended.
- `alembic/` — no change; env.py already reads `DATABASE_URL` from settings.

---

## Topics Investigated

### 1. Base image comparison

| Image | Compressed (Docker Hub) | Uncompressed (typical) | Tesseract | opencv-python | Verdict |
|---|---|---|---|---|---|
| `python:3.11-slim` (Bookworm) | ~45 MB | ~140 MB | ✅ official Debian pkg + `tesseract-ocr-spa` | ✅ manylinux2014 wheel | **Recommended** |
| `python:3.11-slim-trixie` | ~43 MB | ~135 MB | ✅ same, slightly newer Debian | ✅ same | OK, marginally newer base |
| `python:3.12-slim` | ~44 MB | ~140 MB | ✅ | ✅ | OK, but project pins `>=3.11` and uses 3.11 features |
| `python:3.11-alpine` | ~20 MB base | ~50 MB + Python | ⚠️ tesseract-ocr in `community`, requires leptonica + many `-dev` packages at build time; musl wheel compat issues historically for `numpy`/`pymupdf` | ✅ but bigger savings nullified by tesseract chain | **Not recommended** |
| `python:3.12-alpine` | similar | similar | same issues | same | Not recommended |

**Key reasoning:**

- **Tesseract is the deal-breaker for Alpine.** Installing `tesseract-ocr` on Alpine needs: `leptonica-dev`, `libpng-dev`, `libjpeg-turbo-dev`, `libtiff-dev`, `zlib-dev`, `gcc`, `musl-dev`, plus the `tesseract-ocr` package. The build chain adds ~150-200 MB and the resulting image is only ~80-100 MB smaller than slim. The math doesn't work.
- **musl vs glibc wheel issues:** historically `numpy`, `pymupdf`, and `cryptography` had Alpine/musl build problems. Most resolved now, but still a real risk for a small team.
- **Why not 3.12:** the project explicitly tests with 3.11 (mypy config, black target, `requires-python = ">=3.11"`). No reason to bump base image to 3.12 just to get a 1-2 MB savings.
- **Why not `python:3.11-slim-bookworm` explicitly:** the untagged `slim` alias follows the latest stable Debian. As of 2026-06, that's Trixie (Debian 13). Trixie is fine. Pinning to `-bookworm` is more conservative (Debian 12, LTS-ish) and what I'd default to for reproducibility.

**Final recommendation:** `python:3.11-slim-bookworm` (explicit Debian 12 base, Trixie 13 is also fine if the user prefers latest).

### 2. Multi-stage vs single-stage Dockerfile

**Verdict: single-stage is sufficient.**

Rationale:

- This is a pure Python project. There's no compiled C/C++/Rust code, no static binary to strip. Multi-stage shines when you have (a) build tools that are 200+ MB and you want to exclude them from the final image, or (b) compiled artifacts that need a different base.
- The build deps we *do* need (gcc, libpq-dev, etc.) are minimal because everything is on wheels. We can do `pip install --no-cache-dir` in the runtime stage and keep it simple.
- The only "build artifact" is the `site-packages/` tree, which we want in the final image anyway.

**What a single-stage Dockerfile looks like (sketch):**

```dockerfile
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-spa \
        libmagic1 \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY pyproject.toml ./
# If using a lock: COPY pyproject.toml uv.lock* ./
RUN pip install --no-cache-dir .

# Copy app code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
# (no .env — injected at runtime)

# Create non-root user
RUN useradd --create-home --shell /bin/bash --uid 1000 appuser \
    && mkdir -p /app/uploads /app/backup_json /app/exam_images \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" \
    || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Note on `pyproject.toml`-only install:** pip can install from a bare `pyproject.toml` (PEP 517/518). It's a small win for cache invalidation: changing app code doesn't bust the pip layer.

### 3. Non-root user

- **Best practice:** Yes, run as non-root. The official `python` images already create a `python` user (UID 999) in some variants, but on `slim` it varies by version. Safer to create our own.
- **UID/GID:** Use explicit `--uid 1000`. The host user is typically UID 1000 on Linux; binding volumes from a host UID 1000 → container UID 1000 means files written by the container are owned by the host user and don't require `chown` magic.
- **For Windows / macOS Docker Desktop:** UID mapping isn't an issue (Docker Desktop handles it). Explicit UID still works.
- **For rootless Docker / Podman:** if the host user is sub-100000 (rootless default), the in-container UID must match or be in the subuid range. UID 1000 is universally safe for default rootful setups.

**Caveat:** if the host's main user isn't 1000, the volume-mounted `database.db` and `uploads/` will be owned by the in-container `appuser` (UID 1000) and may appear "not yours" on the host. Two solutions:

- Document that the host should `chown -R 1000:1000 ./data` once after first run.
- Or: pass `user: "1000:1000"` in compose, or use Docker's `user` directive.

### 4. Entrypoint strategy

**Three options evaluated:**

| Option | Behavior | Pros | Cons |
|---|---|---|---|
| A. `CMD uvicorn ...` | Lifespan's `create_tables()` runs | Zero complexity. Matches current code. | Doesn't run Alembic migrations. Tables created via `create_all` ignore Alembic's history — the `alembic_version` table stays empty, so future `alembic upgrade` calls may be confused. |
| B. `CMD bash -c "alembic upgrade head && exec uvicorn ..."` | Real migrations run | Correct migration history. Idempotent (Alembic is no-op if up to date). | Slow startup (~1-2s extra). Requires `alembic.ini` to be readable from container CWD. |
| C. Entrypoint script with both | Same as B, more readable | Easy to add `prestart` hooks (wait for DB, etc.) | Extra file to maintain. |

**Recommendation: Option B (inline) is the best fit.**

Reasoning:

- The user has 3 migrations and a clear path to more. The current `lifespan → create_all` pattern is a *first-run convenience* that will silently mask migration drift going forward. Better to fix it now.
- The risk of "what if the DB file is missing": `alembic upgrade head` with a non-existent DB creates the file. ✅ Safe.
- The risk of "what if there's a column drift": Alembic will try to run all migrations. If the DB was already created via `create_all`, the `alembic_version` table won't exist → Alembic runs all migrations from scratch → potential DDL errors on duplicate tables. **Mitigation:** on first run with an existing dev DB, run `alembic stamp head` once, OR start fresh.
- **Concrete advice for the user:** for the first Docker run, if the user wants to keep their existing `database.db`, they need to either (a) stamp it first or (b) start with a fresh DB. Document this in the README.
- If we want zero-risk zero-fuss: keep `create_all` in `lifespan` AND run `alembic upgrade head` in entrypoint. They're both idempotent for "nothing to do." That's belt + suspenders. **My recommendation: pick ONE.** Going with B (Alembic) is the right long-term move; document that `lifespan`'s `create_tables` should be **removed or made conditional** to avoid drift.

**Final choice: Option B with a one-line note that the `lifespan` `create_tables()` call should be revisited in a follow-up change** (it can stay for now, Alembic is the source of truth).

### 5. docker-compose.yml for dev

**Minimal useful dev setup:**

```yaml
services:
  app:
    build: .
    container_name: exam-qa-app
    ports:
      - "8000:8000"
    volumes:
      # Persistent data on the host (NOT inside the image)
      - ./database.db:/app/database.db
      - ./uploads:/app/uploads
      - ./backup_json:/app/backup_json
      - ./exam_images:/app/exam_images
    env_file:
      - .env   # ⚠️ .env is gitignored; that's fine
    environment:
      # Override paths to match the in-container layout (volumes above)
      DATABASE_URL: sqlite+aiosqlite:////app/database.db
      UPLOAD_DIR: /app/uploads
    restart: unless-stopped
```

**Notes:**

- The `env_file: .env` line is fine for local dev (Docker reads the file at compose-up time, never commits it to a layer). The actual `.env` on disk is gitignored.
- The `environment:` block **overrides** `env_file` for the path-related vars. This is important: the app expects `database.db` to live at `/app/database.db` inside the container, not at the host's `./database.db`. Setting `DATABASE_URL` explicitly to the in-container absolute path makes SQLite write into the mounted volume.
- Alternative: change the `.env` to use absolute paths. That works but couples the dev environment to the container layout.
- **Live reload:** not configured by default. To enable, add a bind mount for `./app:/app/app` and override the command to `uvicorn ... --reload`. **Trade-off:** `--reload` watches all files and restarts on any change, including `__pycache__`. For a small project it's fine; for prod it's wrong. I'll document this as an opt-in via a separate `docker-compose.dev.yml` overlay OR an env var like `RELOAD=true`.
- **Don't include the observability stack here.** The user already has `docker-compose.observability.yml`. Two compose files is normal: `docker-compose.yml` (app) + `docker-compose.observability.yml` (monitoring). They can be brought up independently.

### 6. .dockerignore

Based on the existing `.gitignore` and image-build best practices:

```gitignore
# Git / VCS
.git/
.gitignore
.github/
.gitattributes
.gitkeep

# Python (these are in .gitignore already; re-state for safety)
__pycache__/
*.py[cod]
*$py.class
*.so
.venv/
venv/
env/
.pytest_cache/
.coverage
htmlcov/
*.egg-info/
dist/
build/
*.egg

# Secrets (CRITICAL — prevent .env from being baked into image)
.env
.env.*
!.env.example

# Local data files (mounted at runtime, not baked in)
*.db
*.sqlite
*.sqlite3
database.db
uploads/
backup_json/
exam_images/
*.jpg
*.jpeg
*.png
*.gif
*.pdf
!app/static/

# IDE / OS
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# Tests (optional — if you don't run tests in the image, exclude)
# tests/
# .pytest_cache/

# The Dockerfile itself? No, keep it so build works
# The docker-compose files? No, keep them for reference

# Logs
*.log
logs/

# OpenSpec (artifacts, not needed in image)
openspec/
.atl/

# Misc
*.bak
*.tmp
```

**Critical:** `.env` and `.env.*` MUST be excluded to prevent leaking the OpenAI key and Langfuse secrets into any image layer.

### 7. Docker image size estimate

**Single-stage slim, with all deps:**

| Component | Approx. |
|---|---|
| `python:3.11-slim-bookworm` base | ~140 MB |
| `tesseract-ocr` + `tesseract-ocr-spa` (English+Spanish data) | ~80 MB |
| `libmagic1`, `libgl1`, `libglib2.0-0` | ~10 MB |
| Python deps (fastapi, sqlalchemy, pytesseract, pillow, pymupdf, openai, jinja2, structlog, ...) | ~250 MB |
| `opencv-python` (full) | ~80 MB |
| `opencv-python-headless` (alternative) | ~50 MB |
| App code | <1 MB |
| **Total (with opencv-python)** | **~560 MB** |
| **Total (with opencv-python-headless)** | **~530 MB** |

**For comparison:**
- Alpine build: ~350-400 MB (with all the musl/leptonica gymnastics). Saves ~150-200 MB.
- `python:3.11-slim` minimum (no tesseract): ~250 MB.

**Acceptable for this type of app?** Yes. This is a self-hosted, single-user app (no SaaS scale). 500-600 MB is normal for an OCR service. The image will be cached on the host after first pull. CI builds will be slower on first run, fast on subsequent.

**Optimization note:** the opencv-python vs opencv-python-headless swap saves ~30 MB and is a "while we're here" improvement. I'll mention it in the proposal as optional.

### 8. Healthcheck

The app exposes `/health` returning `{"status": "ok", "version": "0.1.0"}` (line 100-103 of `app/main.py`).

**Recommended HEALTHCHECK:**

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).getcode() == 200 else 1)" \
    || exit 1
```

Or simpler using `curl` (if installed, but slim doesn't have it):

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; r = urllib.request.urlopen('http://localhost:8000/health', timeout=3); sys.exit(0 if r.getcode() == 200 else 1)"
```

**Why these params:**
- `--start-period=10s`: gives the app time to start uvicorn + create tables + import opencv (cold start can be 5-10s).
- `--interval=30s`: don't hammer the endpoint.
- `--timeout=5s`: opencv is heavy, the first health hit might be slow.
- `--retries=3`: standard.

**Don't use `wget` or `curl`:** not installed in `slim` by default. Pure Python is portable.

**Better long-term option:** add a dedicated `/health/deep` endpoint that checks DB connectivity. But that's a feature, not containerization scope. Defer.

---

## Approaches Summary

| # | Approach | Pros | Cons | Effort |
|---|---|---|---|---|
| 1 | **`python:3.11-slim-bookworm`, single-stage, non-root UID 1000, alembic entrypoint, opencv-python kept as-is, bind-mount volumes in compose, Python urllib healthcheck** | Battle-tested, no Alpine pain, fast build, ~560 MB, clear migration story | Slightly larger image than Alpine | **Low** |
| 2 | **`python:3.11-slim-bookworm` + `opencv-python-headless` swap in `pyproject.toml`** | ~30 MB smaller; smaller attack surface; aligns with PyPI's own Docker recommendation | Requires editing `pyproject.toml`; minor risk of cv2 API differences (negligible — headless is a drop-in for this use case) | **Low** |
| 3 | **`python:3.11-alpine`, multi-stage, slimmusl tricks** | Smallest image (~400 MB) | Tesseract build chain is painful; musl wheel risks; +2-3 hours of debugging; CI is slower; no real benefit for a 1-user app | **High** |
| 4 | **No entrypoint, rely on lifespan's `create_tables()`** | Simplest | Migration drift; Alembic never runs in container; future `alembic upgrade head` outside container would fail | **Low but wrong** |

---

## Recommendation

**Go with Approach 1** (with optional Approach 2 micro-optimization if the user agrees to edit `pyproject.toml`).

**Concrete deliverables for the proposal:**

1. `Dockerfile` — single-stage, `python:3.11-slim-bookworm`, non-root UID 1000, healthcheck, CMD runs `alembic upgrade head && exec uvicorn ...`.
2. `.dockerignore` — full exclude list, with `.env` and all data dirs excluded.
3. `docker-compose.yml` — minimal dev stack: app service with bind-mounted volumes and env_file.
4. `docker-compose.dev.yml` (overlay) — opt-in live-reload setup for dev (binds `./app` and uses `--reload`).
5. README update — Docker quickstart section in both `README.md` and `README.es.md`. Note: the architecture diagram the user asked for is a *follow-up*, post-Docker.
6. **No code changes** to `app/`, `pyproject.toml`, or `alembic/`. (Exception: if the user wants Approach 2, swap `opencv-python` → `opencv-python-headless` in `pyproject.toml`.)

**Migration note for the user:** if they keep their existing `database.db` when first running the container, they'll need to stamp it (`alembic stamp head` inside the container, or a one-off shell). I'll document this clearly.

**Open questions to surface to the user (the orchestrator should ask ONE at a time):**

1. **OpenCV swap?** Want to switch to `opencv-python-headless` for ~30 MB savings? (Low risk, but a `pyproject.toml` change.)
2. **UID?** OK with 1000? Or do you want it parameterized via build arg?
3. **First-run DB migration handling?** OK to document "either start fresh or stamp head" in the README, or do you want a more automated solution (e.g., a `prestart` script that detects and stamps)?

---

## Risks

- **Secret leakage** if `.dockerignore` is incomplete or someone uses `docker build --secret` wrong. Mitigation: the `.dockerignore` MUST include `.env` and `.env.*`.
- **Migration drift** if `lifespan`'s `create_tables()` and the new `alembic upgrade head` entrypoint both run on every start. Currently: `create_all` is a no-op if tables exist; `alembic upgrade head` is a no-op if up-to-date. ✅ Safe in practice. But it's redundant and confusing. **Follow-up:** remove `create_tables()` from `lifespan` once we're confident in the new entrypoint.
- **SQLite + bind-mount performance** on macOS/Windows (Docker Desktop): the bind-mounted `database.db` will be slower than a Docker volume. Mitigation: in compose, use a named volume (`app_data:/app/data`) for the DB and a bind mount for uploads. Trade-off: harder to inspect from the host. For a 1-user dev setup, the bind mount is fine.
- **Image size** (~560 MB) is on the high side. Acceptable for this app's deployment pattern (self-hosted, infrequent redeploys). Could be reduced with `opencv-python-headless` swap.
- **`tesseract-ocr-spa` adds ~30 MB** for the Spanish language data. Non-negotiable since the app's OCR is configured for Spanish by default.
- **Build cache invalidation** if `pyproject.toml` changes frequently. Mitigation: install Python deps in a separate layer from app code (already in the sketch).

---

## Ready for Proposal

**Yes.** All 8 topics investigated, all recommendations grounded in the actual code, no ambiguity. The orchestrator should propose the Approach 1 deliverable list above and ask the user the 3 open questions (one at a time, per the persona's "one question at a time" rule).

If the user wants to proceed with "recomendado" (their stated preference), the orchestrator can also auto-pick:
- OpenCV: keep as-is for the first cut (zero risk). Headless swap is a tiny follow-up.
- UID: 1000.
- First-run DB: document "start fresh or stamp head" in README.
