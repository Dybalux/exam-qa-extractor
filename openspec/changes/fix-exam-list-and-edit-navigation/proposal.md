---
name: fix-exam-list-and-edit-navigation
status: proposed
created: 2026-07-02
why: |
  Post-save redirects land on entity detail pages instead of list pages, forcing extra clicks.
  Cancel links point to inconsistent targets. No unsaved-changes guard exists. Narrow form
  cards are flush-left on desktop. The answer-reorder form renders raw JSON instead of redirecting.
---

# Change: fix-exam-list-and-edit-navigation

## Why

After creating/editing an exam or question, the browser lands on the entity *detail* page — forcing the user to navigate back to the list to continue CRUD work. Cancel links are inconsistent (`/exams/{id}`, `history.back()`, parent detail mixed targets). Editing a form and accidentally clicking Cancel silently discards work with no warning. Desktop form cards sit flush-left, wasting the wide viewport. The answer-reorder form POSTs to a JSON endpoint and renders raw JSON.

## What Changes

### Backend — redirect targets (`app/api/pages.py`, `app/api/exams.py`)
- **Exam create/edit** → redirect to `/exams` with `_redirect_with_flash("Examen guardado")`.
- **Manual question create** → redirect to `/questions` with `_redirect_with_flash("Pregunta guardada")`.
- **OCR correction submit** → redirect to `/questions` with `_redirect_with_flash("Corrección guardada")`.
- **Answer create/update** → unchanged (parent question detail, no list exists).
- **Image upload** (`upload_exam_image`) → switch to `_redirect_with_flash`. Preserve context-aware destination (review queue or exam detail) via hidden `return_to` input in the upload form.

### Templates — cancel links (7 files)
| Template | Cancel target before → after |
|---|---|
| `exams/form.html` (edit branch) | `/exams/{id}` → `/exams` |
| `questions/manual_form.html` | `/exams/{id}` → `/questions` |
| `questions/correct.html` | `history.back()` → `/questions` |
| `answers/form.html` | already `/questions/{id}` (keep) |
| `questions/bulk_upload.html` | `/exams/{id}` (keep) |
| `answers/manage.html` | `/questions/{id}` (keep) |

### CSS — desktop centering (`app/static/css/styles.css`)
- Add `.form-card { max-width: 520px; margin-inline: auto; }` inside `@media (min-width: 1024px)`.
- Apply class to cards in `exams/form.html`, `answers/form.html`, `questions/bulk_upload.html`.

### JS — dirty tracking + unsaved-changes modal (`app/static/js/app.js`, `app/templates/base.html`)
- Attach `input`/`change` delegation to `[data-track-dirty]` forms; set `data-dirty="true"` on first change.
- Cancel buttons on dirty forms trigger modal (3 actions): **Guardar y salir** (submit form), **Descartar** (navigate), **Cancelar** (close modal).
- Modal reuses existing `.modal` CSS, focus trap, Escape key from delete modal pattern.

### Answer reorder fix (`app/templates/answers/manage.html`)
- JS `fetch` interceptor on reorder form → POST JSON → show toast → redirect to `/questions/{id}`. Replaces raw JSON render.

## Impact

- **UX**: users land on lists, cancel targets are predictable, unsaved edits are protected.
- **Breakage risk**: none — all target routes exist. CSS is additive. JS degrades gracefully.
- **Lines**: ~150–200 across 11 files. Fits under 400-line review budget.

## Approach

1. **Backend**: swap 6 URL strings in POST handlers, replace manual URL construction in `upload_exam_image` with `_redirect_with_flash`.
2. **Templates**: change href values; add `return_to` hidden input to bulk upload.
3. **CSS**: 5-line rule gated by media query.
4. **Dirty tracking**: `input`/`change` events on `document` (delegation). Compare `form.elements` values vs initial snapshot on blur/submit. Reset flag on submit. No `MutationObserver` needed for these forms (no dynamic fields).
5. **Reuse**: `_redirect_with_flash` for all flash messages. Delete modal's `.modal`, `aria-modal`, focus trap, Escape key patterns for unsaved modal.

## Non-Goals / Out of Scope

- Practice sessions, analytics dashboards (not CRUDs).
- Server-side session middleware.
- Horizontal form layouts, batch operations, inline editing.

## Open Questions

None — user decision table resolves all product questions.

## Risks

| Risk | Mitigation |
|---|---|
| Dirty-tracking false positives on date/file inputs | Compare initial vs current value on modal open, not on each keystroke |
| Image upload `return_to` lost on direct navigation | Hidden input is explicit; query-param `?from=` as secondary fallback |
| Answer reorder `fetch` fails with CSP or no-JS | Same-origin POST; degrades to current raw-JSON behavior if JS disabled |
| "Guardar y salir" races with server validation failure | Modal closes, native POST proceeds, server errors re-render form with flash |

## Test Plan (preview)

- **Backend**: pytest assertions on redirect target URLs and flash message content.
- **JS**: unit tests for `data-dirty` flag lifecycle and modal open/close state machine.
- **CSS**: visual regression screenshot for `.form-card` at ≥1024px.
- **Integration**: Playwright smoke test — create exam → redirected to `/exams` with flash; edit with unsaved changes → cancel → modal → discard → list.
