# Archive Report: fix-mypy-baseline

**Change**: fix-mypy-baseline
**Archived**: 2026-07-22
**Artifact store mode**: hybrid (engram + openspec)
**Strict TDD**: not active (standard mode)
**Final verdict**: PASS — change ready for archive

## Executive Summary

- All 79 mypy errors in 10 source files resolved; `mypy app --ignore-missing-imports` reports 0 errors across 62 source files.
- Three latent runtime bugs in the live `POST /api/v1/exams/{id}/upload` endpoint fixed (wrong type to `save_file`, non-existent `process_image` method, non-existent `absolute_path` field) — endpoint was broken at runtime prior to this change.
- Test suite grew from 142 to 158 (16 new tests covering form helper, OCR failure path, BinaryIO contract, and form-file-integration). 4/4 gate commands clean.
- 28/28 implementation tasks complete across 5 phases, including a 5-finding rework round (commit `998287b`) that resolved 2 BLOCKERs, 1 CRITICAL, 1 WARNING, and 1 SUGGESTION.
- New spec domain `type-correctness` (3 requirements, 6 scenarios) added to source of truth.

## Sync Summary

| Domain | Action | Details |
|--------|--------|---------|
| `type-correctness` | Created (new domain) | 3 ADDED requirements, 6 scenarios — full spec copied from delta (delta was a complete spec, not an incremental delta) |

The delta spec `openspec/changes/fix-mypy-baseline/specs/type-correctness/spec.md` was a new full domain spec with only an `## ADDED Requirements` section. Since no prior main spec existed for `type-correctness`, the requirements were copied to `openspec/specs/type-correctness/spec.md` and wrapped in the project's standard domain header (`## Domain: type-correctness (New Capability)`, `### Purpose`, `### Requirements`).

## Source of Truth Updated

The following main spec now reflects the new behavior:

- `openspec/specs/type-correctness/spec.md` (new domain, 3 requirements, 6 scenarios)

## Archive Contents

```
openspec/changes/archive/2026-07-22-fix-mypy-baseline/
├── proposal.md        ✅
├── specs/
│   └── type-correctness/
│       └── spec.md    ✅
├── design.md          ✅
├── tasks.md           ✅ (28/28 tasks complete)
├── apply-progress.md  ✅
└── verify-report.md   ✅
```

## Task Completion

All 28 tasks across 5 phases are marked `[x]` in the persisted `tasks.md` artifact:

- Phase 1 (exams.py runtime bugs + test mocks): 5/5
- Phase 2 (pages.py form helpers + adoption + return types + shuffle): 7/7
- Phase 3 (session.py + json_io_service.py): 4/4
- Phase 4 (remaining mechanical fixes across 6 files + pyproject): 8/8
- Phase 5 (new tests + final verification): 4/4

No stale-checkbox reconciliation was needed.

## Verification Status

| Check | Result |
|-------|--------|
| `uv run mypy app --ignore-missing-imports` | 0 errors in 62 source files |
| `uv run pytest` | 158 passed (142 existing + 16 new) |
| `uv run ruff check app tests` | All checks passed |
| `uv run ruff format --check app tests` | All files already formatted |
| Spec scenarios compliant | 6/6 |
| Design decisions followed | 4/4 |
| CRITICAL findings | 0 |
| BLOCKERs / CRITICAL / WARNING / SUGGESTION | 0 / 0 / 0 / 0 after rework round |

## Rework Round (commit 998287b)

Gate review of the original 5-phase implementation returned 5 findings:

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| 1 | BLOCKER | `isinstance` guard checked wrong `UploadFile` class (fastapi vs starlette base) | Changed import to `starlette.datastructures.UploadFile` in `pages.py` and `test_form_helpers.py` |
| 2 | BLOCKER | `test_form_helpers.py` false-positive suite (constructed `fastapi.UploadFile`) | Switched to `starlette.UploadFile` + added integration test POST `/exams/new` with file in text field |
| 3 | CRITICAL | REQ-TYPE-1 BinaryIO contract not asserted in upload tests | Added `io.IOBase` isinstance + `hasattr(read/seek)` checks in both upload success tests |
| 4 | WARNING | OCR-failure test missed log assertion (REQ-TYPE-1 sc.2) | Added `caplog` assertion verifying "OCR failed" + storage path in warning log |
| 5 | SUGGESTION | `response_model=None` on `/import` dropped OpenAPI contract | Set `response_model=ImportPreviewSchema \| ImportApplyResultSchema` |

All 5 resolved; re-review (observation #362) confirmed PASS.

## Engram Observation Traceability

| Artifact | Observation ID | Sync ID |
|----------|---------------|---------|
| `sdd/fix-mypy-baseline/explore` | #353 | `obs-95485ef5225c70d7` |
| `sdd/fix-mypy-baseline/proposal` | #354 | `obs-dc34cb4492fd6c1c` |
| `sdd/fix-mypy-baseline/spec` | #355 | `obs-260c12783af08568` |
| `sdd/fix-mypy-baseline/design` | #356 | `obs-216828ffa8de4a1e` |
| `sdd/fix-mypy-baseline/tasks` | #357 | `obs-8be9ea66e1e358ed` |
| `sdd/fix-mypy-baseline/apply-progress` | #358 | `obs-5d11edf5c5d5d9e2` |
| `sdd/fix-mypy-baseline/verify-report` | #363 | `obs-d187246aaffe0832` |
| `sdd/fix-mypy-baseline/archive-report` | (this entry) | — |

Related cross-phase observation: #362 (gate re-review decision) — `obs-a1bac7faf9521247`.

## Files Changed (Implementation)

| File | Action | Notes |
|------|--------|-------|
| `app/api/exams.py` | Modified | 3 runtime bug fixes (BytesIO wrap, extract_from_path, storage_path) |
| `app/api/pages.py` | Modified | `_form_str` / `_form_str_or_none` helpers + 31 adoption sites + 11 GET return-type broadenings + shuffle fix + starlette UploadFile import |
| `app/api/import_export.py` | Modified | Return-type union + explicit `response_model` |
| `app/db/session.py` | Modified | `async_sessionmaker` + `AsyncGenerator` annotation |
| `app/db/init_db.py` | Modified | `cast(dict[str, Any], yaml.safe_load(f))` |
| `app/services/json_io_service.py` | Modified | Return annotation + `existing` rename + `Subject` in TYPE_CHECKING |
| `app/services/ocr_service.py` | Modified | Tuple literal `[...]` → `(...)` |
| `app/services/exam_service.py` | Modified | `dict[str, int]` annotation on `topic_counts` |
| `app/db/migrations/versions/004_*.py` | Modified | Function param annotations + `cast` for `Row.first()[0]` |
| `app/db/migrations/versions/005_*.py` | Modified | `(nulls or 0) > 0` scalar guard |
| `pyproject.toml` | Modified | Removed cv2 override, added `types-PyYAML>=6.0` |
| `uv.lock` | Modified | Transitive dep changes from `types-PyYAML` |
| `tests/api/test_form_helpers.py` | Created | 14 parametrized helper tests (starlette UploadFile) |
| `tests/api/test_redirect_targets.py` | Modified | Updated mocks; added BinaryIO assertions, caplog assertion, integration test for file in text field |

## Deviations from Design

| # | Deviation | Impact |
|---|-----------|--------|
| 1 | `OCRProcessingError` used (not `OCRServiceError` as design speculated) | None — matches actual `app/core/exceptions.py` |
| 2 | `response_model=None` on 11 GET handler decorators | Required — FastAPI response model inference error with union return types |
| 3 | `Subject` added to `TYPE_CHECKING` block in `json_io_service.py` | Required — mypy needs it for the new return annotation |
| 4 | `response_model=ImportPreviewSchema \| ImportApplyResultSchema` on `/import` (rework) | Explicit union replaces `None`; all import tests pass with this explicit union |

## Discoveries

- The actual OCR exception class is `OCRProcessingError` (not `OCRServiceError`). Verification must read `app/core/exceptions.py` rather than trust design speculation.
- FastAPI's `UploadFile` re-export does NOT inherit from `starlette.datastructures.UploadFile` the way the parser instances do. Form helpers MUST isinstance-check the starlette base class or they will fail to catch files the parser actually produces. This is a non-obvious inheritance fact and a likely future regression source — captured in the spec as a behavioral requirement.
- FastAPI rejects route handlers whose return annotation is a union including `RedirectResponse` unless `response_model=None` is set on the route decorator. The 11 GET handlers in `app/api/pages.py` required this decorator tweak to pass mypy with broadened return types.
- `mypy app --ignore-missing-imports` now scans 62 source files (up from 62 before the fix — the file count is unchanged; the count of files containing errors dropped from 10 to 0). `types-PyYAML` was needed in dev deps to remove a residual Any from `yaml.safe_load`.

## Active Changes State

After this archive, the active `openspec/changes/` directory contains 3 unrelated changes:

- `fix-exam-list-and-edit-navigation`
- `openai-vision-integration`
- `openai-vision-ocr`

None touch the `type-correctness` domain, so no spec conflicts.

## SDD Cycle Status

**CLOSED.** The change has been fully planned, implemented, verified, and archived. Ready for the next change.
