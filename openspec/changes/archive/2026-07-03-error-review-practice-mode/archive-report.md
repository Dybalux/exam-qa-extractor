# Archive Report: error-review-practice-mode

**Change**: error-review-practice-mode
**Archived**: 2026-07-03
**Artifact store mode**: hybrid (engram + openspec)
**Strict TDD**: not active (standard mode)
**Final verdict**: PASS WITH WARNINGS — change ready for archive

## Executive Summary

The `error_review` practice mode is fully implemented, verified, and archived. Users can now select an "Error Review" practice mode that restricts the question pool to questions they have previously answered incorrectly (`is_correct = False`). The change is additive: no existing mode is affected, no schema change beyond expanding the `check_valid_practice_mode` CHECK constraint, and no data migration required. 142 tests pass, ruff is clean, and mypy introduced 0 new errors.

## Sync Summary

| Domain | Action | Details |
|--------|--------|---------|
| `practice-modes` | Created (new domain) | 6 requirements, 14 scenarios — full spec copied from delta (delta was a complete spec, not an incremental delta) |

The delta spec `openspec/changes/error-review-practice-mode/specs/practice-modes/spec.md` was a full domain spec with no `ADDED`/`MODIFIED`/`REMOVED`/`RENAMED` sections. Since no prior main spec existed for `practice-modes`, it was copied verbatim to `openspec/specs/practice-modes/spec.md`.

## Source of Truth Updated

The following main spec now reflects the new behavior:
- `openspec/specs/practice-modes/spec.md` (new domain, 6 requirements, 14 scenarios)

## Archive Contents

```
openspec/changes/archive/2026-07-03-error-review-practice-mode/
├── exploration.md     ✅
├── proposal.md        ✅
├── specs/
│   └── practice-modes/
│       └── spec.md    ✅
├── design.md          ✅
└── tasks.md           ✅ (14/14 tasks complete)
```

## Task Completion

All 14 tasks across 4 phases are marked `[x]` in the persisted `tasks.md` artifact:

- Phase 1 (Foundation): 3/3 — enum, constraint, migration
- Phase 2 (Core Implementation): 4/4 — helper, signature change, create_session branch, get_next_question branch
- Phase 3 (Frontend Wiring): 2/2 — radio option, validation error handling
- Phase 4 (Testing): 5/5 — unit + integration tests for service + API

No stale-checkbox reconciliation was needed.

## Verification Status

| Check | Result |
|-------|--------|
| `uv run pytest tests/` | 142 passed, 0 failed |
| `uv run ruff check app/ tests/` | All checks passed |
| `uv run mypy app/` | 0 new errors (80 pre-existing in unrelated files) |
| Spec scenarios compliant | 14/14 |
| Design decisions followed | 3/3 |
| CRITICAL findings | 0 |
| Warnings | 1 (W1) |
| Suggestions | 1 (S1) |

### Recorded Warnings & Suggestions

- **W1 (low impact)**: No integration test for the topic filter scenario (REQ-PM-2 topic filter). Code path verified by unit test of `_get_failed_question_ids` + filter logic; integration coverage for the topic path is missing. Acceptable for archive; future enhancement.
- **S1 (low impact)**: `practice_create()` catches `ValidationError` broadly. Could be narrowed to specific business-rule errors. Low impact, deferred.

Both are non-blocking. No CRITICAL findings exist.

## Engram Observation Traceability

| Artifact | Observation ID | Sync ID |
|----------|---------------|---------|
| `sdd/error-review-practice-mode/proposal` | #336 | `obs-619a489c0162c58a` |
| `sdd/error-review-practice-mode/spec` | #339 | `obs-2b851261357e670e` |
| `sdd/error-review-practice-mode/tasks` | #340 | `obs-c732351661c151a9` |
| `sdd/error-review-practice-mode/apply-progress` | #346 | `obs-7d93f7ea806bdfc8` |
| `sdd/error-review-practice-mode/verify-report` | #348 | `obs-d3d1edfd76f3d686` |
| `sdd/error-review-practice-mode/archive-report` | (this entry) | — |

## Files Changed (Implementation)

| File | Action |
|------|--------|
| `app/core/constants.py` | Modified — added `ERROR_REVIEW = "error_review"` to `PracticeMode` |
| `app/models/practice_session.py` | Modified — expanded `check_valid_practice_mode` |
| `app/db/migrations/versions/006_add_error_review_mode.py` | Created — Alembic migration |
| `app/services/practice_service.py` | Modified — new helper, param, branches |
| `app/templates/practice/start.html` | Modified — added radio option |
| `app/api/pages.py` | Modified — wrapped with try/except ValidationError |
| `tests/unit/services/test_practice_service.py` | Created — 2 unit tests |
| `tests/integration/api/test_practice.py` | Created — 3 integration tests |

## Discoveries

- `default_subject` fixture in conftest.py loads the Subject before the Topic is added, so `.topics` relationship is stale in async contexts. Direct DB query via `select(Topic)` is the safe pattern when using this fixture in new tests. Captured in apply-progress and is now part of the project's test conventions.
- The `retry_of` column on `PracticeResponse` is unused for this change but is a natural hook for future spaced-repetition features.

## Deviations from Design

None — implementation matches design exactly.

## Notes for Future Sessions

- The verify report and apply-progress are persisted only in Engram (not in `openspec/changes/.../verify-report.md`). The archive folder contains `proposal.md`, `exploration.md`, `specs/`, `design.md`, and `tasks.md` only. This is consistent with the SDD skill behavior for this project.
- The active changes directory now has 3 active changes: `fix-exam-list-and-edit-navigation`, `openai-vision-integration`, `openai-vision-ocr`. None touch the `practice-modes` domain, so no spec conflicts.

## SDD Cycle Status

**CLOSED.** The change has been fully planned, implemented, verified, and archived. Ready for the next change.
