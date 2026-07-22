# Apply Progress: fix-mypy-baseline

## Status: success (rework round complete)

## Executive Summary
- **Rework round**: 5 findings from gate review — all resolved
- All 28 original tasks across 5 phases already complete
- Final mypy: 0 errors in 62 source files
- Final pytest: 158 tests passing (142 existing + 16 new: 14 form helper + 1 OCR-failure + 1 form-file-integration)
- Ruff check: clean. Ruff format: all files formatted.

## Rework Round — Gate Review Findings (2026-07-22)

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| 1 | BLOCKER | isinstance guard checks wrong UploadFile class (fastapi vs starlette base) | Changed import to starlette.datastructures.UploadFile in pages.py and test_form_helpers.py |
| 2 | BLOCKER | test_form_helpers.py false-positive suite (constructs fastapi.UploadFile) | Changed to starlette.UploadFile + added integration test POST /exams/new with file in text field |
| 3 | CRITICAL | REQ-TYPE-1 BinaryIO contract not asserted in upload tests | Added io.IOBase isinstance + hasattr(read/seek) checks in both upload success tests |
| 4 | WARNING | OCR-failure test misses log assertion (REQ-TYPE-1 sc.2) | Added caplog assertion verifying "OCR failed" + storage path in warning log |
| 5 | SUGGESTION | response_model=None on /import drops OpenAPI contract | Set response_model=ImportPreviewSchema \| ImportApplyResultSchema |
| 6 | — | cast assert in migration 004 | SKIPPED per instructions |

## Commits (6 work-unit commits)

| # | Commit | Phase | Files |
|---|--------|-------|-------|
| 1 | 1999ac9 | Phase 1 | app/api/exams.py, tests/api/test_redirect_targets.py |
| 2 | 936e3a4 | Phase 2 | app/api/pages.py |
| 3 | ec21611 | Phase 3 | app/db/session.py, app/services/json_io_service.py |
| 4 | d8e4c79 | Phase 4 | app/api/import_export.py, app/services/ocr_service.py, app/services/exam_service.py, app/db/init_db.py, migration 004, migration 005, pyproject.toml, uv.lock |
| 5 | 5e53699 | Phase 5 | tests/api/test_form_helpers.py (new), tests/api/test_redirect_targets.py, openspec/changes/fix-mypy-baseline/tasks.md |
| 6 | 998287b | Rework | app/api/pages.py, app/api/import_export.py, tests/api/test_form_helpers.py, tests/api/test_redirect_targets.py |

## Files Changed (rework round)

| File | Action | What Was Done |
|------|--------|---------------|
| `app/api/pages.py` | Modified | Changed UploadFile import from fastapi to starlette.datastructures (base class catches parser instances) |
| `app/api/import_export.py` | Modified | Set explicit response_model=ImportPreviewSchema \| ImportApplyResultSchema |
| `tests/api/test_form_helpers.py` | Modified | Changed UploadFile import to starlette.datastructures |
| `tests/api/test_redirect_targets.py` | Modified | Added BinaryIO assertions (2 upload tests), caplog assertion (OCR-failure test), integration test for file in text field |

## Test Results

| Check | Result |
|-------|--------|
| `uv run mypy app --ignore-missing-imports` | 0 errors in 62 source files |
| `uv run pytest` | 158 passed |
| `uv run ruff check app tests` | All checks passed |
| `uv run ruff format --check app tests` | All files already formatted |

## Deviations from Design

1. **OCR exception class**: `OCRProcessingError` (not `OCRServiceError` as design speculated) — verified against `app/core/exceptions.py`
2. **response_model=None**: Required on 11 GET handler decorators to prevent FastAPI response model inference error with union return types (`HTMLResponse | RedirectResponse`)
3. **Subject type in TYPE_CHECKING**: Added `Subject` to `json_io_service.py` TYPE_CHECKING block to satisfy mypy with the new return annotation
4. **(rework) response_model on /import**: Now `ImportPreviewSchema | ImportApplyResultSchema` (was `None`) — app boots and all import tests pass with this explicit union

## Risks

- None. All verification gates passed. No push/PR created.
