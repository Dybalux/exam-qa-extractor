# container-runtime Specification

## Purpose

Defines how the `exam-qa-extractor` Docker image is composed, started,
and configured at runtime. Covers the production compose stack, the
development overlay, the entrypoint migration logic, and the contract
for environment variable injection without leaking secrets into image
layers.

## Requirements

### Requirement: Production Compose Stack

`docker-compose.yml` MUST define a single `app` service that builds
from the local `Dockerfile`, exposes port 8000, mounts the host
directories `./data/db`, `./data/uploads`, and `./data/backups` into
the container, and reads environment variables from a host-side
`.env` file via `env_file`.

#### Scenario: Clean one-command startup

- GIVEN a clean clone with `./data/{db,uploads,backups}` pre-created
  and a valid `.env` file at the repository root
- WHEN `docker compose up -d` is run
- THEN the `app` service starts and reaches a `(healthy)` state
- AND port 8000 on the host is bound to port 8000 in the container

#### Scenario: Bind mounts persist across restarts

- GIVEN a running container that has written a file to the uploads
  volume
- WHEN `docker compose restart app` is executed
- THEN the uploaded file is still present on the host under
  `./data/uploads`
- AND the SQLite database under `./data/db` is still readable
- AND backups under `./data/backups` are preserved

#### Scenario: Port 8000 exposed on host

- GIVEN a running stack
- WHEN `curl -fsS http://localhost:8000/health` is run from the host
- THEN the response is HTTP 200 with a JSON body
- AND `docker compose ps` reports port mapping `8000:8000`

### Requirement: Environment Variable Injection

Runtime configuration (including `OPENAI_API_KEY`) MUST reach the
container exclusively through `env_file`, and `.env` MUST NOT appear
in any image layer.

#### Scenario: Secrets available at runtime

- GIVEN a `.env` file containing `OPENAI_API_KEY=sk-test-...`
- WHEN the container starts
- THEN the `OPENAI_API_KEY` environment variable is set inside the
  container (`docker compose exec app printenv OPENAI_API_KEY`
  returns the value)

#### Scenario: Secret absent from image layers

- GIVEN a built image
- WHEN `docker history --no-trunc exam-qa-extractor:test` is
  inspected
- THEN no layer's `CREATED BY` column references `.env`
- AND `docker run --rm exam-qa-extractor:test printenv
  OPENAI_API_KEY` exits with code 1 (variable unset in the image)
- AND `.dockerignore` contains entries that block `.env*` files

### Requirement: Development Overlay

`docker-compose.dev.yml` MUST extend the base stack with live-reload
behavior for `app/` code changes, and MUST be invokable via
`docker compose -f docker-compose.yml -f docker-compose.dev.yml up`.

#### Scenario: Overlay enables autoreload

- GIVEN the dev overlay in use
- WHEN the stack is started
- THEN the `app` process is launched with uvicorn `--reload`
- AND changes to files under `./app/` trigger a process restart
  observable in `docker compose logs -f app`

#### Scenario: Dev overlay does not override volumes silently

- GIVEN the dev overlay in use
- WHEN `docker compose -f docker-compose.yml -f docker-compose.dev.yml
  config` is run
- THEN bind mounts for `data/db`, `data/uploads`, and `data/backups`
  are still present in the resolved configuration

### Requirement: Entrypoint Migration Logic

`docker/entrypoint.sh` MUST own database schema initialization and
MUST handle three distinct states of an existing database before
launching the application: fresh install, existing DB without
`alembic_version`, and existing DB with `alembic_version`.

#### Scenario: Fresh install (no database file)

- GIVEN the host `./data/db` directory is empty
- WHEN the container starts
- THEN the entrypoint creates a new SQLite database
- AND runs `alembic upgrade head`
- AND the `alembic_version` table is created and stamped at the
  latest revision
- AND all expected tables (e.g. `documents`, `questions`) exist

#### Scenario: Existing DB without alembic_version

- GIVEN a pre-existing SQLite database under `./data/db` that has
  application tables but NO `alembic_version` table
- WHEN the container starts
- THEN the entrypoint stamps the database at the latest revision
  (so the schema is declared "managed") WITHOUT dropping data
- AND THEN runs `alembic upgrade head`
- AND application data is preserved

#### Scenario: Existing DB with alembic_version

- GIVEN a pre-existing database with an `alembic_version` table at
  some prior revision
- WHEN the container starts
- THEN the entrypoint runs `alembic upgrade head`
- AND pending migrations are applied in order
- AND the application launches only after migrations succeed

#### Scenario: Migration failure aborts startup

- GIVEN a migration that fails (e.g. conflicting schema)
- WHEN the entrypoint runs `alembic upgrade head`
- THEN the script exits non-zero
- AND the application process is NOT started
- AND the container exits, surfacing the migration error in
  `docker compose logs app`

### Requirement: Host UID Compatibility

Bind-mounted host directories MUST be usable by the container's
non-root user (UID 1000). The project MUST document the
`chown -R 1000:1000 ./data` remediation for hosts where the default
user is not UID 1000.

#### Scenario: Mismatched host UID is documented

- GIVEN a host where the active user is not UID 1000
- WHEN the user follows the README quickstart
- THEN they are instructed to run `chown -R 1000:1000 ./data`
  (or the compose-equivalent) before `docker compose up`
- AND after doing so, no `Permission denied` errors appear in
  container logs

#### Scenario: Pre-chowned directory works

- GIVEN `./data` is owned by UID 1000 on the host
- WHEN the stack is started
- THEN the entrypoint can write the SQLite database under
  `./data/db`
- AND uploads written by the app appear on the host with UID 1000
  ownership

### Requirement: Image Reproducibility

The runtime stack MUST be reproducible from version-controlled files
only — `Dockerfile`, `docker-compose.yml`, `docker-compose.dev.yml`,
`docker/entrypoint.sh`, and `pyproject.toml`. Building and starting
the stack MUST NOT require any file outside the repository (`.env`
excepted, since it contains secrets and is git-ignored).
