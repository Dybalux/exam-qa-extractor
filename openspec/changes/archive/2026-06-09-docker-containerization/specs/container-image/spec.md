# container-image Specification

## Purpose

Defines the build contract and runtime expectations for the Docker image
that ships `exam-qa-extractor`. The image MUST be reproducible on any
host with Docker Engine ≥ 24, MUST run the FastAPI + OCR service as a
non-root user, and MUST stay under 600 MB.

## Requirements

### Requirement: Base Image and System Dependencies

The image MUST be built from `python:3.11-slim-bookworm` and MUST
install the system packages required by the OCR pipeline and the
OpenCV runtime: `tesseract-ocr`, `tesseract-ocr-spa`, `libmagic1`,
`libgl1-mesa-glx`, and `libglib2.0-0`.

#### Scenario: Clean build from base

- GIVEN a clean Docker cache and the repository root
- WHEN `docker build -t exam-qa-extractor:test .` is run
- THEN the build completes successfully
- AND the resulting image is based on `python:3.11-slim-bookworm`
- AND `tesseract --version` reports a non-empty version string
- AND `tesseract --list-langs` includes `spa`

#### Scenario: OpenCV shared libraries present

- GIVEN a built image
- WHEN the runtime container is started
- THEN `ldconfig -p | grep -E 'libGL|libglib'` returns at least one
  matching entry
- AND `import cv2` inside the container does not raise
  `ImportError` or `OSError` for missing GLib/GL libraries

### Requirement: Python Dependency Installation

The image MUST install Python dependencies declared in `pyproject.toml`
using `pip install --no-cache-dir`, and the resulting environment MUST
include `opencv-python-headless` (NOT `opencv-python`).

#### Scenario: Dependencies resolved from pyproject

- GIVEN the project `pyproject.toml` at the repository root
- WHEN the build runs the `pip install` step
- THEN `pip install .` (or equivalent) completes without compile
  errors
- AND no `gcc` / `build-essential` invocation is required (wheels only)

#### Scenario: OpenCV headless is the installed variant

- GIVEN a built image
- WHEN `pip show opencv-python-headless` runs inside the container
- THEN it reports the package as installed
- AND `pip show opencv-python` reports the package as NOT installed
- AND `cv2.getGui*` symbols are unavailable (headless confirms drop-in)

### Requirement: Non-Root User

The image MUST create and use a non-root user with UID 1000 for both
file ownership and process execution.

#### Scenario: Container runs as UID 1000

- GIVEN a built image started with default configuration
- WHEN `id` is run inside the running container
- THEN the output reports `uid=1000` and an associated group with
  `gid=1000`
- AND the process tree's PID 1 is owned by that user

#### Scenario: Bind mounts are writable by UID 1000

- GIVEN a host directory owned by UID 1000 (or pre-chowned via
  `chown -R 1000:1000 ./data`)
- WHEN the container writes to a bind-mounted path
- THEN the write succeeds without `Permission denied` errors

### Requirement: Working Directory and Application Code

The image MUST set `WORKDIR /app` and MUST copy the application source
and Alembic migrations into that directory. Build layers MUST be
ordered so that dependency installation is cached independently from
source code changes.

#### Scenario: WORKDIR and entry paths resolve

- GIVEN a built image
- WHEN `pwd` and `ls /app` run inside the container
- THEN `pwd` prints `/app`
- AND `/app/app/` and `/app/alembic/` directories exist
- AND `/app/pyproject.toml` exists

#### Scenario: Source change does not invalidate pip layer

- GIVEN a previously built image
- WHEN a single file under `/app/app/` is modified and the image is
  rebuilt
- THEN the `pip install` step is reported by BuildKit as cached
- AND only the COPY step for source is re-executed

### Requirement: Healthcheck

The image MUST declare a `HEALTHCHECK` that probes the application's
`/health` HTTP endpoint.

#### Scenario: HEALTHCHECK directive present

- GIVEN a built image
- WHEN `docker inspect --format '{{json .Config.Healthcheck}}'`
  the-image is run
- THEN a non-null `Healthcheck` object is returned
- AND the `Test` array contains `curl` (or `python -c`) hitting
  `http://localhost:8000/health`

#### Scenario: Container reports healthy after startup

- GIVEN a freshly started container with the application listening
  on port 8000
- WHEN `docker ps` is queried after the startup interval elapses
- THEN the container's status includes `(healthy)`
- AND `docker inspect --format '{{.State.Health.Status}}'` returns
  `healthy`

### Requirement: Image Size Budget

The built image MUST be no larger than 600 MB.

#### Scenario: Image size under budget

- GIVEN a built image
- WHEN `docker images exam-qa-extractor:test --format
  '{{.Size}}'` is run
- THEN the reported size is ≤ 600 MB

#### Scenario: No dev/test tooling in image

- GIVEN a built image
- WHEN `pip list` is inspected inside the container
- THEN `pytest`, `ruff`, `mypy`, and other dev-only groups from
  `pyproject.toml` are NOT installed (production-only install)
