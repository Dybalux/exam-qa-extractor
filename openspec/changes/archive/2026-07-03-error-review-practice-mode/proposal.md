# Proposal: Error Review Practice Mode

## Intent

Users need a dedicated way to practice questions they've previously answered incorrectly. Today the app has four practice modes (random, by_partial, by_topic, exam_simulation) but no way to focus on mistakes. This mode lets users target their weak spots using existing answer history — no new data model required.

## Scope

### In Scope
- Add `PracticeMode.ERROR_REVIEW = "error_review"` enum value
- New `_get_failed_question_ids()` helper in `PracticeService` querying `PracticeResponse` where `is_correct=False`
- Branch in `_get_available_questions()` to restrict to failed question IDs when mode is `error_review`
- Radio option in `practice/start.html` for error review mode
- Alembic migration expanding the `check_valid_practice_mode` constraint
- Edge case: no failed questions → flash message "Todavía no tenés errores para revisar."

### Out of Scope
- Weighted selection by failure count
- Time-decay or spaced-repetition algorithms
- Marking questions as "cleared" after successful error-review session
- UI changes to `results.html` (deferred enhancement)

## Capabilities

### New Capabilities
- `practice-modes`: Error review mode for practicing previously-failed questions

### Modified Capabilities
None. Existing practice modes are unchanged; this is additive.

## Approach

Simple binary: any question the user has ever answered with `is_correct=False` is eligible, regardless of later correct answers. A new helper queries `PracticeResponse` filtered by `user_session_id` and `is_correct=False`, deduplicates by `question_id`, optionally filters by `exam_id`/`topic`. In `_get_available_questions()`, if mode is `error_review`, intersect available questions with the failed set.

When no failed questions exist, `_get_available_questions()` returns empty, triggering the existing `ValidationError` path that the controller catches to flash a message.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/core/constants.py` | Modified | Add `ERROR_REVIEW` to `PracticeMode` enum |
| `app/models/practice_session.py` | Modified | Expand `check_valid_practice_mode` constraint |
| `app/services/practice_service.py` | Modified | New helper + mode branch in `_get_available_questions` |
| `app/templates/practice/start.html` | Modified | Add radio option for error review |
| `app/db/migrations/versions/` | New | Alembic migration for constraint update |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Migration fails in production | Low | Constraint expansion is idempotent; rollback reverts the single line |
| Performance at scale with many responses | Low | Index on `(user_session_id, is_correct)` exists; current scale is small |
| UX confusion about "error review" definition | Low | Label + description in radio card: "Preguntas que alguna vez respondiste mal" |

## Rollback Plan

Downgrade the Alembic migration to restore the previous constraint. Remove the enum value and revert the helper — no data migration needed.

## Dependencies

None. All data is already present in the database.

## Success Criteria

- [ ] User can select "Error review" mode and start a session
- [ ] Session includes only previously-failed questions
- [ ] Filters (exam, topic) correctly narrow the failed question pool
- [ ] Missing failed questions shows a clear, helpful flash message
- [ ] All existing modes continue working unchanged
