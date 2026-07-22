# Apply Progress: fix-exam-list-and-edit-navigation

## Status: Complete (23/23 tasks, 1 manual)

### Completed (x22)

#### Phase 1: Foundation
- [x] 1.1 Create `app/api/_flash.py` — `redirect_with_flash` with `urllib.parse.quote`
- [x] 1.2 Update `pages.py` — replace local `_redirect_with_flash` with import
- [x] 1.3 Hoist `showToast`/`escapeHtml`/`toastContainer` out of delete-modal IIFE to global
- [x] 1.4 Add `.form-card` CSS centering rule in `@media (min-width: 1024px)`

#### Phase 2: Backend Redirect Targets
- [x] 2.1 `exam_create` → `/exams` with "Examen guardado"
- [x] 2.2 `exam_edit_submit` → `/exams` with flash (was bare RedirectResponse)
- [x] 2.3 `manual_question_create` → `/questions` with "Pregunta guardada"
- [x] 2.4 `question_correct_submit` → `/questions` with "Corrección guardada"
- [x] 2.5 `upload_exam_image` `return_to` param + open-redirect validation
- [x] 2.6 Convert 6 flash-bearing redirects in `upload_exam_image` to `redirect_with_flash`

#### Phase 3: Templates
- [x] 3.1 `exams/form.html` — cancel links, form-card, data-track-dirty
- [x] 3.2 `questions/manual_form.html` — cancel links, data-track-dirty
- [x] 3.3 `questions/correct.html` — history.back() → /questions, data-track-dirty
- [x] 3.4 `answers/form.html` — form-card, data-track-dirty
- [x] 3.5 `questions/bulk_upload.html` — form-card, data-track-dirty, return_to hidden input
- [x] 3.6 `base.html` — #unsaved-modal markup

#### Phase 4: JavaScript
- [x] 4.1 Dirty tracking IIFE — input/change event delegation on [data-track-dirty]
- [x] 4.2 Cancel-link interception — two-tier (data-cancel-for + closest)
- [x] 4.3 Unsaved modal handlers — open/close, Guardar/Descartar/Cancelar, focus trap
- [x] 4.4 Reorder fetch interceptor — prevent default POST, fetch JSON, toast + redirect

#### Phase 5: Tests + Spec
- [x] 5.1 Test `redirect_with_flash` URL-encoding (special chars)
- [x] 5.2 Test `return_to` open-redirect validation
- [x] 5.3 Test redirect target URLs (exam_create, exam_edit, manual_q, OCR correction)
- [x] 5.4 Amend `form-interaction/spec.md` — flag false "Reorder degrades" scenario

### Pending (manual)
- [ ] 5.5 Manual JS testing — dirty flag lifecycle, modal behaviour, reorder fetch contract

## Commits
| Hash | Description |
|------|-------------|
| `13c327b` | refactor(api): extract shared flash helper, fix post-save redirects, add return_to validation |
| `415189e` | feat(ui): center form cards, update cancel links, add unsaved modal markup |
| `402b359` | feat(js): hoist toast helpers, add dirty tracking, unsaved modal, reorder fetch |
| `5fc8da3` | test: add redirect target tests, amend reorder degradation spec |
| `07230a2` | fix: address judgment-day findings (cache-bust, focus traps, return_to producer, test coverage) |

## Files Changed
| File | Changes |
|------|---------|
| `app/api/_flash.py` | Created — shared redirect_with_flash helper |
| `app/api/pages.py` | Modified — import + 4 redirect target swaps + _redirect_with_flash removal |
| `app/api/exams.py` | Modified — return_to param + _validate_return_to + 6 redirect conversions |
| `app/static/css/styles.css` | Modified — .form-card rule inside @media (min-width:1024px) |
| `app/static/js/app.js` | Modified — hoisted helpers + new IIFE (dirty/modals/reorder/focus trap) |
| `app/templates/base.html` | Modified — #unsaved-modal markup |
| `app/templates/exams/form.html` | Modified — cancel links, form-card, data-track-dirty |
| `app/templates/questions/manual_form.html` | Modified — cancel links, data-track-dirty |
| `app/templates/questions/correct.html` | Modified — cancel links, data-track-dirty |
| `app/templates/answers/form.html` | Modified — form-card, data-track-dirty |
| `app/templates/questions/bulk_upload.html` | Modified — form-card, data-track-dirty, return_to |
| `app/templates/answers/manage.html` | Modified — data-question-id |
| `tests/api/test_redirect_targets.py` | Created — 11 tests |
| `openspec/.../specs/form-interaction/spec.md` | Modified — spec amendment |

## Test Results
- All 137 tests pass (134 pre-existing + 3 new: answer redirect, upload return_to valid, upload return_to default)
- ruff check: all passed
- mypy: 80 pre-existing errors, 0 new errors introduced

## Judgment-Day Fixes (commit `07230a2`)
| ID | Finding | Fix |
|----|---------|-----|
| C1 | JS cache-buster not bumped | `base.html` `?v=3` -> `?v=4` |
| C2 | Missing answer create/edit redirect test | Added `test_answer_create_redirects_to_parent_question` |
| C3 | Buggy OCR-correction test assertion | Decode full location, assert exact flash message |
| S1 | Focus trap escapes after pointer click | `trapFocus` pulls focus back inside modal when `activeElement` is outside |
| S2 | `return_to` dead code (no producer) | Added `?return_to=` to upload links in `exams/detail.html` and `list.html` |
| S3 | Delete-modal focus trap inert when confirmBtn disabled | Focus close button instead of disabled confirm button |
| S4 | Missing endpoint-level return_to test + misleading docstring | Added 2 upload endpoint tests + fixed docstring |
| G1 | Dead code in exam-edit redirect test | Removed orphaned `create_resp`/`list_resp` block |
| G2 | Dead no-op guard `link.type === 'submit'` | Removed guard from cancel-link interceptor |

### Follow-up note (S2)
The `?return_to=/exams` producer on `exams/list.html` is added as instructed,
but `/exams` (without ID) is not in the `_validate_return_to` allowlist
(only `/search/needs-review` and `/exams/{id}` are allowed). The list-page
return_to will be rejected by the current validator and fall back to the
default redirect. The `exams/detail.html` links (`?return_to=/exams/{id}`)
work correctly. `manual_form.html:97` left untouched per instructions.
