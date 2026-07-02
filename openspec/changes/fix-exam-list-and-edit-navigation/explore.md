# Exploration: fix-exam-list-and-edit-navigation

## Current State

The project uses FastAPI with Jinja2 template responses for HTML pages and a separate REST API (`app/api/exams.py`) for JSON consumers. Page routes live in `app/api/pages.py`. Exam-related templates are under `app/templates/exams/`. Styling is entirely custom CSS in `app/static/css/styles.css` (no Bootstrap / Tailwind — uses BEM-ish utility classes like `.form-group`, `.form-label`, `.btn`, `.card`).

Redirects elsewhere in the app follow two patterns:
1. `_redirect_with_flash(url, message, msg_type)` — wraps a 303 redirect with query-param flash.
2. `RedirectResponse(url=..., status_code=303)` — plain redirect (or 302 for NotFound fallbacks).

Both patterns are imported from `fastapi.responses`.

## Affected Areas

### Issue 1 — Post-save redirect bug
- **File**: `app/api/pages.py`
  - Line 148: `exam_create` (POST `/exams/new`) returns `_redirect_with_flash(f"/exams/{exam.id}", ...)`.
  - Line 221: `exam_edit_submit` (POST `/exams/{exam_id}/edit`) returns `RedirectResponse(url=f"/exams/{exam_id}", status_code=303)`.
- **Current behavior**: After creating or editing an exam, the browser lands on the exam **detail** page (`/exams/{id}`).
- **Desired behavior**: After creating or editing, redirect to the exam **list** page (`/exams`).

### Issue 2 — Cancel-from-edit redirect bug
- **File**: `app/templates/exams/form.html`
  - Line 5: Cancel button in `page_actions` block links to `'/exams/' + exam.id|string` when `exam` is present (edit mode).
  - Line 40: Inline cancel link inside the `<form>` uses the same conditional href.
- **Current behavior**: Clicking Cancel while editing an exam navigates to the exam **detail** page.
- **Desired behavior**: Clicking Cancel from edit should return to the exam **list** page (`/exams`).
- **Note**: The create (new-exam) case already correctly links to `/exams`, so only the edit branch needs changing.

### Issue 3 — Desktop label alignment bug
- **File**: `app/templates/exams/form.html` (and potentially `app/static/css/styles.css`)
- **Current behavior**: The exam form is wrapped in a `.card` with an inline `style="max-width:520px"`. On desktop (`≥1024px`), `.page-body` has `padding: 24px 32px`. Because the card is narrow and **not centered**, it sits at the far left of the wide content area. The labels are `display: block` above full-width inputs — technically aligned within the card, but the card itself feels visually “misaligned” against the broad desktop canvas.
- **Desired behavior**: On desktop, the form card should be visually centered (or better proportioned) so labels and inputs appear balanced.
- **Related code**: No existing `.mx-auto` or centering utility exists in `styles.css`. Other forms either fill the width (`questions/manual_form.html` uses `.grid-2`) or also use a narrow card (`answers/form.html` has `max-width:560px` with the same left-alignment issue).

## Existing Patterns

- **Redirects**: The app consistently redirects to the *resource detail* page after mutation (e.g., answer create → `/questions/{id}`, manual question create → `/questions/{id}`). Changing exam redirects to the *list* page is a deliberate UX deviation requested by the user.
- **Forms**: All forms use stacked `display: block` labels + inputs inside `.card` containers. There is no desktop-specific horizontal form layout in the codebase.
- **Cancel links**: Most cancel links in the app go to the parent resource detail page (e.g., answer cancel → `/questions/{id}`). Changing the exam edit cancel to the list page is also a requested deviation.

## Approaches

### Approach A — Minimal surgical fixes
- In `pages.py`: change two redirect URLs from detail to list.
- In `form.html`: change two `href` expressions from detail to list when `exam` is truthy.
- In `form.html` or `styles.css`: add `margin: 0 auto` to the card on desktop (e.g., via a small `@media (min-width: 1024px) { .form-card { margin-inline: auto; } }` rule and add that class to the card).
- **Pros**: Smallest footprint, respects existing architecture.
- **Cons**: The CSS centering is a one-off; other narrow cards (`answers/form.html`) have the same visual issue but are out of scope.
- **Effort**: Low (~5–7 lines across 3 files).

### Approach B — Broader form-card consistency
- Same redirect/cancel fixes as Approach A.
- Extract the inline `max-width` cards into a reusable `.form-card` class that centers itself on desktop and caps width on all viewports.
- Apply the new class to both `exams/form.html` and `answers/form.html` so the fix is systematic.
- **Pros**: Fixes the root pattern, not just the symptom; improves both exam and answer forms.
- **Cons**: Touches an extra template (`answers/form.html`) slightly expanding scope.
- **Effort**: Low-Medium (~8–12 lines across 4 files).

## Recommendation

**Approach A** for the redirect/cancel fixes (minimal and unambiguous). For the CSS alignment, **Approach B** is preferable if the review budget allows — adding a `.form-card` utility class in `styles.css` and applying it to the exam form is clean, but if we want to stay razor-focused on the three reported issues, Approach A’s inline/desktop media-query addition is acceptable.

Given the 400-line review budget and the tiny line count, either approach is safe. I lean toward **Approach B** for the CSS because it prevents the same bug report from resurfacing for the answer form.

## Risks

- The edit and create flows share `exams/form.html`; changing the Cancel `href` conditionally (`if exam`) is already how the template works, so the edit-only fix is low risk.
- No existing tests cover the HTML page redirect targets for exams — changing them won’t break CI, but we should verify manually or add a lightweight test.
- The CSS centering change is purely visual; it does not affect mobile layout because the media query can be scoped to `min-width: 1024px`.
- If the user *intended* a horizontal label/input grid on desktop (rather than centering), the current CSS has no infrastructure for that and the effort would jump to Medium. Based on the existing stacked pattern across all forms, centering the card is the most consistent interpretation.

## Ready for Proposal

Yes. The scope is small (3 files, <15 lines), the fixes are straightforward, and there are no blockers.
