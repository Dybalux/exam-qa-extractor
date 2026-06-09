# Proposal: Docker containerization

## Intent

Ship a reproducible Docker image for `exam-qa-extractor` so the FastAPI +
OCR service runs identically on any host. Today it only runs from a
local venv — fragile, blocks one-command onboarding.

## Scope

**In:** `Dockerfile` (single-stage, `python:3.11-slim-bookworm`, UID 1000,
`alembic upgrade head && exec uvicorn`); `.dockerignore` (blocks `.env*`,
`*.db`, data dirs, caches, `openspec/`); `docker-compose.yml` (app +
bind-mounts + `env_file`); `docker-compose.dev.yml` (`--reload` overlay);
`docker/entrypoint.sh` (stamps existing DBs then migrates); README
quickstart in EN + ES; `pyproject.toml` swap to `opencv-python-headless`
(~30 MB).

**Out:** removing `lifespan.create_tables()` (follow-up); Alpine,
multi-stage, k8s, CI, architecture diagram.

## Capabilities

### New Capabilities
- `container-image`: build contract, runtime expectations, healthcheck.
- `container-runtime`: compose stack, persistence model, dev overlay,
  env injection.

### Modified Capabilities
None. `app/`, `alembic/`, `app/config.py` are untouched.

## Approach

- **Base**: `python:3.11-slim-bookworm`. Alpine rejected (tesseract
  build chain + musl wheel risk outweigh ~150 MB savings).
- **Single-stage**: pure-Python, no compiled artifacts to strip.
- **Layer caching**: `pyproject.toml` → `pip install` → app code.
- **Migrations**: entrypoint is source of truth. `lifespan`'s
  `create_all` stays (idempotent) and is removed later.
- **OpenCV**: `pyproject.toml` swap only; headless is a drop-in for
  non-GUI cv2.

## Affected Areas

| Area | Impact |
|------|--------|
| `Dockerfile` | New |
| `.dockerignore` | New (secret guard) |
| `docker-compose.yml` | New |
| `docker-compose.dev.yml` | New |
| `docker/entrypoint.sh` | New |
| `pyproject.toml` | Modified (`opencv-python` → `-headless`) |
| `README.md`, `README.es.md` | Modified (quickstart) |
| `app/`, `alembic/` | Unchanged |
| `docker-compose.observability.yml` | Unchanged |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `.env` (`OPENAI_API_KEY`) baked into image | Med | `.dockerignore` blocks `.env*`; runtime uses `env_file` |
| `create_all` + `alembic upgrade head` both run | Low | Both idempotent; entrypoint stamps existing DBs |
| Bind-mount UID mismatch on non-1000 host | Med | README documents `chown -R 1000:1000 ./data` |
| SQLite latency over bind mount (mac/Win) | Low | Acceptable for single-user dev |
| `opencv-python-headless` API regression | Low | Drop-in for non-GUI cv2 |
| Image size ~530 MB | Low | Acceptable for self-hosted app |

## Rollback Plan

Delete the image, remove the five new files, revert `opencv-python*` and
the README diffs. No host data is touched (DB + uploads live on bind
mounts). A single `git revert` restores everything.

## Dependencies

Docker Engine ≥ 24 + Compose v2; `tesseract-ocr` + `-spa` in
`slim-bookworm`; `opencv-python-headless` ≥ 4.8 with cp311 manylinux2014
wheels (no build toolchain in image).

## Success Criteria

- [ ] `docker compose up` reaches `/health` 200 on a clean clone.
- [ ] Fresh volume applies all 3 Alembic migrations + stamps
      `alembic_version`.
- [ ] Pre-existing DB (no `alembic_version`) is stamped, then migrated.
- [ ] `.env` reaches the container at runtime but never appears in
      image layers (`docker history` clean).
- [ ] Dev overlay live-reloads on `app/` edits.
- [ ] Image ≤ 600 MB; no `pytest`/`ruff` regression after headless swap.
- [ ] README quickstart works end-to-end for a new developer.
