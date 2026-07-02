# Broader Exploration: fix-exam-list-and-edit-navigation

> This report supersedes `explore.md` for the expanded scope decided by the user.

---

## 1. CRUD Inventory

| Entity | Create Route (GET → POST) | Edit Route (GET → POST) | List Route | Current Save Redirect | Current Cancel Target |
|---|---|---|---|---|---|
| **Exam** | `/exams/new` → `POST /exams/new` (`exam_create`) | `/exams/{id}/edit` → `POST /exams/{id}/edit` (`exam_edit_submit`) | `/exams` | `/exams/{id}` (detail) | `/exams/{id}` (detail) |
| **Question (manual)** | `/exams/{id}/questions/new` → `POST /exams/{id}/questions/new` (`manual_question_create`) | — (no edit page; only OCR correction) | `/questions` | `/questions/{id}` (detail) | `/exams/{id}` (exam detail) |
| **Question (OCR correct)** | — | `/questions/{id}/correct` → `POST /questions/{id}/correct` (`question_correct_submit`) | `/questions` | `/questions/{id}` (detail) | `javascript:history.back()` |
| **Answer** | `/questions/{qid}/answers/new` → `POST …/answers/new` (`answer_create`) | `/questions/{qid}/answers/{aid}/edit` → `POST …/edit` (`answer_update`) | **None** (answers live on question detail) | `/questions/{qid}` (question detail) | `/questions/{qid}` (question detail) |
| **Image (bulk upload)** | `/exams/{id}/upload` → `POST /api/v1/exams/{id}/upload` (`upload_exam_image`) | — | **None** | `/exams/{id}` or `/search/needs-review?exam_id={id}` | `/exams/{id}` (exam detail) |
| **Answer reorder** | — | `POST /api/v1/answers/question/{qid}/reorder` (from `answers/manage.html`) | — | Returns JSON (no redirect) | — |

**Key finding**: Only Exams and Questions have a dedicated list page. Answers and Images do not have their own list pages; they are children of Questions/Exams and are managed from the parent detail page.

---

## 2. Frontend Stack Summary

| Layer | Technology | Notes |
|---|---|---|
| **Templating** | Jinja2 (server-rendered) | All HTML pages are `TemplateResponse` from FastAPI. |
| **JS runtime** | Vanilla JS | Single file `app/static/js/app.js` (~445 lines). No HTMX, Alpine.js, jQuery, React. |
| **CSS** | Custom CSS | Single file `app/static/css/styles.css` (~609 lines). Custom properties, BEM-ish classes, small utility layer (`.flex`, `.gap-3`, etc.). No Bootstrap / Tailwind. |
| **Form submission** | Plain HTML POST | Every form uses `method="POST"` and standard browser submission. No Fetch/HTMX for forms. |
| **Modal** | **Present** (delete modal) | Hardcoded in `base.html`, styled in `styles.css`, wired in `app.js`. Has header, body, warning, checkbox, footer, animations, focus management, keyboard (Escape). Can be adapted. |
| **Toast/flash** | **Present** (dual system) | Server: query-param flash (`_redirect_with_flash`) rendered as `.alert` in `base.html`. Client: `showToast(type, message)` in `app.js` with `#toast-container` in `base.html`. Toasts currently used only for delete success. |
| **Unsaved-changes guard** | **Absent** | No `beforeunload` listener, no dirty-form tracking, no cancel-with-unsaved-changes dialog. |

---

## 3. Backend Patterns Summary

| Pattern | Implementation | Notes |
|---|---|---|
| **Redirects** | `fastapi.responses.RedirectResponse` | 303 for successful POST-redirect-GET; 302 for error fallbacks (NotFound). |
| **Flash messages** | Query-param based | `_redirect_with_flash(url, message, msg_type)` appends `?message=…&type=…`. `_get_flash_from_query(request)` parses it. No server-side session middleware. |
| **Form validation** | Manual | `await request.form()` reads fields; validation is hand-written (e.g., `manual_question_create` builds an `errors` list). Pydantic schemas are used only for REST API JSON endpoints, not for page POSTs. |

---

## 4. Scope Estimate

### Files that must change

1. **`app/api/pages.py`** — 6–7 POST endpoints need redirect target changes + flash message updates.
2. **`app/api/exams.py`** — 1 POST endpoint (`upload_exam_image`) needs redirect review.
3. **`app/templates/exams/form.html`** — cancel link + centering fix.
4. **`app/templates/questions/manual_form.html`** — cancel link.
5. **`app/templates/answers/form.html`** — cancel link + centering fix.
6. **`app/templates/questions/correct.html`** — cancel link (currently `history.back()`).
7. **`app/templates/questions/bulk_upload.html`** — cancel link + potential redirect change.
8. **`app/static/css/styles.css`** — add `.form-card` centering utility (desktop ≥1024px).
9. **`app/static/js/app.js`** — add dirty-form tracking + unsaved-changes modal logic.
10. **`app/templates/base.html`** — optionally add a reusable cancel/unsaved modal markup (or reuse delete modal structure programmatically).

### Line-count estimate

| Area | Lines (approx) |
|---|---|
| Python redirect/flash changes | ~20–30 |
| Template cancel-link changes | ~10–15 |
| CSS centering utility | ~5–10 |
| JS dirty tracking + modal | ~80–120 |
| New modal markup (if needed) | ~20–30 |
| **Total** | **~135–205 lines** |

### Single PR or chained?

**Yes — single PR fits under the 400-line budget.** The change is ~200 lines at the high end. However, it is multi-domain (Python backend, 5 templates, CSS, JS). If the review budget is strict, it could be split into two chained PRs:
- **PR 1**: Redirects, cancel links, flash messages, CSS centering (~80–120 lines).
- **PR 2**: Unsaved-changes modal and dirty-form JS (~80–120 lines).

---

## 5. Open Product Questions

Organized by priority (must be answered before `sdd-propose`):

1. **For child entities without a list page (answers, images), where should post-save redirect go?**
   Answers and images have no standalone list page; they are managed inside the parent detail. Should answer create/edit redirect to `/questions` (all questions list), `/questions/{id}` (parent question detail), or stay on the parent detail? This blocks the "consistent across all CRUDs" requirement.

2. **Should the OCR correction form (`/questions/{id}/correct`) redirect to `/questions` or back to `/search/needs-review`?**
   Users typically arrive at the correction page from the review queue. Redirecting to the generic question list may break their workflow.

3. **Should image upload post-save redirect to `/exams` (list) or remain context-aware (exam detail / review queue)?**
   After uploading, the user usually wants to see extraction results or go to the review queue. Forcing the exam list feels disruptive.

4. **Does "Guardar y salir" in the cancel modal also trigger a flash toast, or is it silent?**
   This affects whether we reuse the existing query-param flash or need a hybrid JS toast after an async save-then-navigate.

5. **Does the desktop centering fix apply to ALL narrow form cards (`answers/form.html`, `bulk_upload.html`) or only `exams/form.html`?**
   The user explicitly complained about the exam form, but the expanded scope says "all CRUDs". Clarification prevents scope creep.

6. **Are practice sessions and analytics dashboards in scope?**
   They have POST forms (`/practice`, `/practice/{id}/answer`) but are workflow/interaction flows, not traditional CRUD entities. The post-save redirect for practice is intentionally to the next question or results page.

7. **The answer-reorder form (`answers/manage.html`) POSTs to a JSON API and receives raw JSON back — is fixing this in scope?**
   It is technically a "save" form with a save button, but it currently lacks a redirect and likely breaks on normal browser submission. If we apply the consistent pattern, it needs special handling.

---

## 6. Non-Obvious Discoveries

- **Dual flash system**: The app has both server-side query-param alerts and client-side JS toasts. The delete modal uses the toast system; everything else uses the alert system. The new "Entidad guardada" flash should probably use the alert system (consistent with existing POST redirects) unless we switch everything to toasts.
- **No session middleware**: Flash cannot be server-side session-based without adding `SessionMiddleware`. Query-param flash is the only option that fits the current architecture without new dependencies.
- **Answer reorder bug**: The reorder form in `answers/manage.html` does a standard browser POST to `/api/v1/answers/question/{id}/reorder`, which returns JSON. There is no JS intercept. This likely results in a blank JSON page on submit. It is orthogonal but worth surfacing.
- **Cancel link inconsistency**: Cancel targets vary arbitrarily — exam form goes to exam detail, manual question form goes to exam detail, answer form goes to question detail, correct form uses `history.back()`, bulk upload goes to exam detail. Making them all go to "list" pages requires deciding what "list" means for child entities.
- **History.back() in correct form**: Using `history.back()` means the cancel target depends on the user's browser history. If they opened the correct page from a direct link, back might go to an external site. Replacing it with an explicit URL is safer.

---

## 7. Recommendation

- **Redirects**: Use query-param flash (existing `_redirect_with_flash`) with entity-specific messages. Do not introduce session middleware.
- **Cancel modal**: Reuse the existing modal CSS/JS infrastructure in `base.html` and `app.js`. Add a generic "unsaved changes" modal alongside the delete modal, or generalize the delete modal into a multi-purpose dialog.
- **Centering**: Add a `.form-card` CSS class with `margin-inline: auto` on desktop and apply it to every narrow form card (`exams/form.html`, `answers/form.html`, `questions/bulk_upload.html`). This is ~8 lines of CSS and 3 template changes.
- **Scope split**: If the user wants the unsaved-changes modal, recommend splitting into two PRs because it introduces new JS behavior (dirty tracking) that deserves focused review.
