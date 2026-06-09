# Archive Report: docker-containerization

**Change**: docker-containerization
**Status**: archived
**Mode**: openspec (B1)
**Verdict**: PASS-WITH-WARNINGS
**Archived on**: 2026-06-09

## Cycle status

The docker-containerization change is fully planned, implemented, verified, and
archived. Ready for the next change.

## Commits on main

| Hash | Subject |
|------|---------|
| `90beddd` | chore: add Docker foundation (.dockerignore, entrypoint, opencv-headless) |
| `a1515d2` | feat(docker): add Dockerfile, compose stack, and runtime config |
| `9aac69c` | docs: add Docker quickstart to README (EN + ES) |
| `702430d` | docs: align Spanish Docker quickstart with voseo tone |

All four commits on `main`, oldest → newest.

## Verification summary

- **Verdict**: PASS-WITH-WARNINGS
- **14** scenarios verified (non-daemon)
- **12** scenarios require manual verification with a Docker daemon (operator checklist in tasks.md Phase 4)
- **0** failed
- **83/83** tests green (`uv run pytest` outside Docker after opencv headless swap)

The 12 daemon-only scenarios cover image build, runtime healthcheck, the three
migration states, secrets-not-leaked into image layers, and the dev overlay live
reload. They are documented in `tasks.md` Phase 4 for an operator to run on a
host with Docker Engine ≥ 24 + Compose v2.

## Specs synced to source of truth

`openspec/changes/docker-containerization/specs/` defined two **new** capabilities
(no prior main specs existed for these domains). Both are full specs (not deltas)
and were copied directly into `openspec/specs/`:

| Domain | Action | Details |
|--------|--------|---------|
| `container-image` | Created | 6 requirements, 13 scenarios (build contract, base image + OCR deps, pip install with opencv-python-headless, UID 1000, WORKDIR + app code, HEALTHCHECK, image ≤ 600 MB) |
| `container-runtime` | Created | 6 requirements, 13 scenarios (production compose stack, env_file injection, dev overlay, entrypoint 3-state migration, UID host compatibility, reproducibility) |

The following specs now reflect the new behavior as the source of truth:
- `openspec/specs/container-image/spec.md`
- `openspec/specs/container-runtime/spec.md`

## Final artifacts (preserved in archive)

- `proposal.md` — Intent, scope, capabilities, risks, rollback
- `explore.md` — Pre-proposal research (base image, multi-stage, OpenCV, entrypoint)
- `design.md` — Technical design (Dockerfile, compose, entrypoint, layer caching)
- `specs/container-image/spec.md` — Build contract
- `specs/container-runtime/spec.md` — Runtime contract
- `tasks.md` — 4 phases, 12 implementation tasks (all `[x]`), 6 verification tasks (all `[x]` under explicit orchestrator override)
- `archive-report.md` — This document

## Task Completion Gate — exceptional reconciliation

Per the sdd-archive Task Completion Gate, implementation tasks must be checked
before sync. Phase 1–3 tasks were already checked by the prior `sdd-apply` runs
(corresponding to commits 90beddd, a1515d2, 9aac69c). Phase 4 (items 4.1–4.6)
was **NOT** ticked in any prior step:

- Items 4.1–4.5 require a Docker daemon and could not be executed in this
  environment.
- Item 4.6 (pytest outside Docker) was executed as part of CI verification.

The orchestrator (user) explicitly authorized mechanical reconciliation of the
unchecked Phase 4 checkboxes based on the verify report summary, and asked
that the operator checklist stay in `tasks.md` for manual confirmation. This
deviation from the default gentle-ai stricter policy is recorded here per the
sdd-archive contract.

## Known follow-ups

1. **Remove `lifespan.create_tables()`** once Docker is the canonical
   deployment. The proposal explicitly scoped this out; both `create_all` and
   `alembic upgrade head` are currently idempotent. After Docker is the
   default, `create_all` becomes redundant and can be deleted.
2. **Architecture diagram** in both `README.md` and `README.es.md` — explicit
   user request, deferred to a post-Docker change. The user wants a visual
   diagram of how the application components (FastAPI, SQLite, OpenCV,
   pytesseract, OpenAI Vision) fit together.
3. **Re-evaluate `opencv-python-headless` dependency** — the apply phase
   confirmed that PIL handles all image I/O in the OCR path and no `cv2.*`
   call site was touched. If `opencv-python-headless` is not actually used by
   any module, dropping it would shrink the image by ~30 MB and simplify
   the build.

## Change folder location

`openspec/changes/docker-containerization/`
→ moved to →
`openspec/changes/archive/2026-06-09-docker-containerization/`

## SDD cycle complete

The change has been fully planned (propose + spec + design + tasks), implemented
(apply × 3 phases, 4 commits), verified (PASS-WITH-WARNINGS), and archived.
The source of truth for both new capabilities now lives in `openspec/specs/`.
Ready for the next change.
