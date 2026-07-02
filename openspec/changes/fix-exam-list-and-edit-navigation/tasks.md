# Tasks: Fix Exam List and Edit Navigation

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~250–350 across 13 files |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR (most changes are additive or string-replacement; JS IIFE is ~80 lines, shared helper extraction is ~30 lines) |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Backend redirects + shared flash helper | PR 1 | `app/api/_flash.py` (create), `pages.py` (4 URL swaps), `exams.py` (return_to + 6 redirect conversions) |
| 2 | Template cancel links + CSS centering | PR 2 | 5 templates (cancel hrefs, form-card class, inline style removal, dirty-tracking attrs, return_to hidden input) |
| 3 | JS: hoist helpers + dirty tracking + modal + reorder | PR 3 | `app.js` refactor (hoist showToast/escapeHtml), new IIFE (dirty tracking, cancel interception, unsaved modal, reorder fetch), `base.html` (#unsaved-modal markup) |
| 4 | Tests + spec amendment | PR 4 | Pytest for flash helper, return_to validation, redirect URLs; amend spec scenario for no-JS reorder |

## Phase 1: Foundation / Infrastructure

- [x] 1.1 Create `app/api/_flash.py` with `redirect_with_flash(url, message, msg_type)` extracted from `pages.py:_redirect_with_flash`; apply `urllib.parse.quote` to both `message` and `msg_type` before concatenation. *(Design decision 9, spec: POST-SAVE REDIRECT)* ~15 lines, low risk

- [x] 1.2 Update `app/api/pages.py`: replace local `_redirect_with_flash` with `from app.api._flash import redirect_with_flash`; update all 4 call sites (lines 148, 221, 334, 457) to use the imported function. *(Design decision 9)* ~10 lines, low risk

- [x] 1.3 Hoist `showToast`, `escapeHtml`, and `toastContainer` out of the delete-modal IIFE in `app/static/js/app.js` to global scope (attach to `window`). Keep existing IIFE functional. *(Design decision 9)* ~20 lines, medium risk (refactor of existing code)

- [x] 1.4 Add `.form-card` centering rule inside `@media (min-width: 1024px)` in `app/static/css/styles.css`: `.form-card { max-width: 520px; margin-inline: auto; }`. *(Design decision 8, spec: DESKTOP FORM CENTERING)* ~5 lines, low risk

## Phase 2: Backend Redirect Targets

- [x] 2.1 `exam_create` (pages.py:148): change redirect target from `f"/exams/{exam.id}"` to `"/exams"` with message `"Examen guardado"`. *(Spec: Exam create redirects to exam list)* ~2 lines, low risk

- [x] 2.2 `exam_edit_submit` (pages.py:221): change from bare `RedirectResponse(url=f"/exams/{exam_id}", status_code=303)` to `redirect_with_flash("/exams", "Examen guardado")`. **Note**: this is a CONVERSION to `redirect_with_flash`, not just a URL swap — the current handler has NO flash. *(Spec: Exam edit redirects to exam list)* ~3 lines, low risk

- [x] 2.3 `manual_question_create` (pages.py:457): change redirect target from `f"/questions/{question.id}"` to `"/questions"` with message `"Pregunta guardada"`. *(Spec: Manual question create redirects to question list)* ~2 lines, low risk

- [x] 2.4 `question_correct_submit` (pages.py:334): change redirect target from `f"/questions/{question_id}"` to `"/questions"` with message `"Corrección guardada"`. *(Spec: OCR correction redirects to question list)* ~2 lines, low risk

- [x] 2.5 `upload_exam_image` (exams.py): add `return_to: str | None = Form(None)` parameter + `from fastapi import Form` import. Validate `return_to` on success path: parse with `urllib.parse.urlsplit`, reject non-empty `.netloc`/`.scheme`, match path against allowlist (`/search/needs-review` exact OR `/exams/\d+` via `re.fullmatch`), pin `exam_id` from route param. Pass validated `return_to` to `redirect_with_flash` on success only. *(Design decision 6)* ~30 lines, high risk (open-redirect vulnerability mitigation)

- [x] 2.6 Convert ALL 6 flash-bearing redirect paths in `upload_exam_image` (exams.py) to `redirect_with_flash`: success (line 205) + 5 error paths (no-filename :145, OCR-failed :165, FileValidationError :210, StorageError :216, generic Exception :222). Each error path keeps its safe default target (`/exams/{id}` or `/exams/{id}/upload`), never consults `return_to`. Leave bare `NotFoundError` redirect (:141, no flash) unchanged. *(Design decision 6)* ~20 lines, medium risk

## Phase 3: Template Changes (Cancel Links + CSS + Dirty Attrs)

- [x] 3.1 `app/templates/exams/form.html`: (a) Header cancel (line 5): change href `{{ '/exams/' + exam.id|string if exam else '/exams' }}` → `/exams`, add `data-cancel-for="exam-form"`. (b) In-form Cancel (line 40): same href change → `/exams`. (c) Add `form-card` to wrapping `<div class="card">` (line 9 → `<div class="card form-card">`). (d) Remove inline `style="max-width:520px"` from wrapping div. (e) Add `id="exam-form"` and `data-track-dirty` to `<form>`. *(Design decision 2+3+8, spec: CANCEL LINK)* ~6 lines, low risk

- [x] 3.2 `app/templates/questions/manual_form.html`: (a) Header cancel (line 6): `/exams/{{ exam.id }}` → `/questions`, add `data-cancel-for="manual-question-form"`. (b) In-form Cancel (line 68): same href change → `/questions`. (c) Add `data-track-dirty` to form (reuse existing `id="manual-question-form"` at line 15 — do NOT duplicate). *(Design decision 2+3, spec: CANCEL LINK)* ~4 lines, low risk

- [x] 3.3 `app/templates/questions/correct.html`: (a) Header cancel (line 6): `javascript:history.back()` → `/questions`, add `data-cancel-for`. (b) In-form Cancel (line 48): same change → `/questions`. (c) Add `data-track-dirty` + `id` to form. *(Design decision 2+3, spec: CANCEL LINK)* ~4 lines, low risk

- [x] 3.4 `app/templates/answers/form.html`: (a) Header cancel (line 6): href unchanged (`/questions/{{ question.id }}` is correct) + add `data-cancel-for`. (b) In-form Cancel (line 48): unchanged. (c) Add `form-card` to wrapping `<div class="card">` (line 10 → `<div class="card form-card">`). (d) Remove inline `style="max-width:560px"` from wrapping div. (e) Add `data-track-dirty` + `id` to form. *(Design decision 2+3+8, spec: CANCEL LINK)* ~5 lines, low risk

- [x] 3.5 `app/templates/questions/bulk_upload.html`: (a) Header cancel (line 6): add `data-cancel-for="bulk-upload-form"`. (b) Add `form-card` to wrapping `<div class="card">` (line 10 → `<div class="card form-card">`). (c) Remove inline `style="max-width:560px"` from wrapping div. (d) Add `id="bulk-upload-form"` and `data-track-dirty` to form (line 12). (e) Add hidden `<input type="hidden" name="return_to" value="{{ request.query_params.get('return_to', '') }}">`. **Note**: the GET handler `bulk_upload_page` must pass `return_to` from query params to template context, or this hidden input is dead code. *(Design decision 6, spec: Image upload preserves return_to)* ~6 lines, medium risk

- [x] 3.6 `app/templates/base.html`: Add `#unsaved-modal` markup after `#delete-modal` (line 133), reusing `.modal` CSS patterns. Include `aria-modal="true"`, `role="dialog"`, backdrop, close button, 3 action buttons ("Guardar y salir", "Descartar", "Cancelar"). *(Design decision 4, spec: UNSAVED CHANGES GUARD)* ~30 lines, low risk

## Phase 4: JavaScript — Dirty Tracking + Modal + Reorder

- [x] 4.1 Add new IIFE in `app/static/js/app.js` for dirty tracking: `input`/`change` event delegation on `document`, matching `[data-track-dirty]` forms; set `data-dirty="true"` on first modification; clear on submit. *(Design decision 3, spec: UNSAVED CHANGES GUARD)* ~20 lines, low risk

- [x] 4.2 Add cancel-link interception (two-tier) in the same IIFE: Tier 1 — intercept `[data-cancel-for]` clicks, look up form via `document.getElementById(link.dataset.cancelFor)`, open modal if form is `data-dirty="true"`. Tier 2 — intercept in-form Cancel clicks via `link.closest('form[data-track-dirty]')`, same modal routing. *(Design decision 3)* ~25 lines, medium risk

- [x] 4.3 Add `openUnsavedModal(href)` / `closeUnsavedModal()` handlers: show/hide `#unsaved-modal`, wire "Guardar y salir" → `form.submit()`, "Descartar" → `window.location = href`, "Cancelar"/Escape → close. Add Tab-trap keydown handler + focus restoration to trigger on close for BOTH delete modal and `#unsaved-modal`. *(Design decision 3+4, spec: UNSAVED CHANGES GUARD)* ~40 lines, medium risk

- [x] 4.4 Add reorder fetch interceptor: intercept `#reorder-form` submit, prevent default, `fetch` POST with `{"ordered_ids": [...]}` (Content-Type: application/json), show toast on success → `window.location` redirect to `/questions/{qid}` (parsed from form `action` or `data-question-id`). On failure → error toast, stay on page. Pre-fill hidden `ordered_ids` from DOM order on page load. *(Design decision 7, spec: ANSWER REORDER FETCH REDIRECT)* ~30 lines, medium risk

## Phase 5: Testing + Spec Amendment

- [ ] 5.1 Pytest: test `redirect_with_flash` URL-encoding — messages with `&`, `#`, spaces, non-ASCII (e.g. `ó`) produce well-formed redirect URLs. *(Design decision 9)* ~15 lines, low risk

- [ ] 5.2 Pytest: test `return_to` open-redirect validation in `upload_exam_image` — `return_to="//evil.com"`, `return_to="https://evil.com"`, `return_to="/unknown"` → fallback default used; valid `return_to="/exams/999"` → redirect to that path. *(Design decision 6)* ~20 lines, medium risk

- [ ] 5.3 Pytest: test redirect target URLs in `exam_create`, `exam_edit_submit`, `manual_question_create`, `question_correct_submit` — assert redirect URL contains correct path and flash query params. *(Spec: POST-SAVE REDIRECT)* ~20 lines, low risk

- [ ] 5.4 Amend `form-interaction/spec.md`: flag scenario "Reorder degrades without JavaScript" as FALSE (no-JS path 422s today). Recommend dropping the degradation scenario and stating that reorder requires JavaScript. *(Design decision 7, open question W1)* ~3 lines, low risk

- [ ] 5.5 Manual JS testing: verify dirty flag lifecycle (set on input/change, clear on submit), unsaved modal open on dirty+Cancel, Escape key closes modal, Tab-trap cycles focus, focus restoration on close, reorder POST body contract and redirect target. *(Spec: UNSAVED CHANGES GUARD + ANSWER REORDER)*
