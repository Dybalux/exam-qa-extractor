# Proposal: fix-mypy-baseline

## Intent

Make CI mypy pass: fix all 79 type errors across 10 files. Three are real latent runtime bugs in `app/api/exams.py` on a live endpoint (`/api/v1/exams/{id}/upload`): wrong type to `save_file`, non-existent OCR method, non-existent field.

## Scope

### In Scope
- All 79 mypy errors → clean `mypy app` (0 errors)
- 3 latent runtime bugs in `upload_exam_image`
- Update tests to match corrected interface
- Remove unused `cv2` override from `pyproject.toml`

### Out of Scope
- Tightening mypy config, refactoring unrelated code, new features, per-file exemptions

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None — type annotations and bug fixes do not change spec-level behavior.

## Approach

Per-file, minimal-diff fixes. No architectural changes.

| Priority | File | Fix |
|----------|------|-----|
| 1 | `app/api/exams.py` | `io.BytesIO(file_data)`, `extract_from_path(storage_path)` |
| 2 | `app/api/pages.py` | `_form_str`/`_form_str_or_none` helpers for 41 `form.get()` sites + return type broadening |
| 3 | `app/db/session.py` | `async_sessionmaker` + `AsyncGenerator` |
| 4 | `app/services/json_io_service.py` | Return annotation + rename shadowed `existing` |
| 5–10 | Remaining 6 files | Mechanical annotations, casts |

Tests: mocks `process_image`/`absolute_path` → `extract_from_path`/`storage_path`.

## Affected Areas

| Area | Change |
|------|--------|
| `app/api/exams.py` | 3 runtime bug fixes |
| `app/api/pages.py` | 41 type-narrowing fixes |
| `app/api/import_export.py` | Return type |
| `app/db/session.py` | Async session + generator type |
| `app/db/init_db.py` | Cast YAML return |
| `app/services/json_io_service.py` | Rename + annotation |
| `app/services/ocr_service.py` | Tuple literal |
| `app/services/exam_service.py` | Dict annotation |
| `app/db/migrations/versions/004_*.py` | Function annotations |
| `app/db/migrations/versions/005_*.py` | Scalar cast |
| `pyproject.toml` | Remove cv2 override |
| `tests/api/test_redirect_targets.py` | Update mocks |

Estimate: **~80–100 lines** (under 400-line budget).

## Risks

| Risk | Mitigation |
|------|------------|
| `exams.py` fix changes live endpoint behavior | Endpoint already broken (would raise `AttributeError`); fix restores intended behavior. Update tests, run full suite. |
| Test mock drift | Only `test_redirect_targets.py` affected; update in same commit. |
| `_form_str` edge case: file under text-field name | Old code crashed, new code returns default — acceptable. |
| `async_sessionmaker` regression | SQLAlchemy 2.0 standard; existing tests catch regressions. |

## Rollback Plan

`git revert` — no migrations, no data changes.

## Dependencies

- `types-PyYAML` added to dev dependencies.

## Success Criteria

- [ ] `mypy app --ignore-missing-imports` → 0 errors
- [ ] `pytest` → 142 tests pass
- [ ] `ruff check` → no new issues
- [ ] CI green
