# Form Interaction Specification

## Purpose

Define unsaved-changes protection, desktop form-card centering, and answer-reorder fetch handling for CRUD forms.

## Requirements

### Requirement: UNSAVED CHANGES GUARD

When a user attempts to cancel a form with unsaved changes, the system MUST prompt for confirmation before discarding work.

#### Scenario: Clean form cancel navigates directly

- GIVEN a form with no field modifications
- WHEN the user clicks Cancel
- THEN the browser navigates to the cancel target without a prompt

#### Scenario: Dirty form cancel triggers modal

- GIVEN a form with at least one modified field
- WHEN the user clicks Cancel
- THEN an unsaved-changes modal appears with three actions: Save and Leave, Discard, and Stay

#### Scenario: Save and Leave submits the form

- GIVEN the unsaved-changes modal is open
- WHEN the user clicks "Guardar y salir"
- THEN the form is submitted via native POST and the page navigates on success

#### Scenario: Discard navigates without saving

- GIVEN the unsaved-changes modal is open
- WHEN the user clicks "Descartar"
- THEN the modal closes and the browser navigates to the cancel target without submitting

#### Scenario: Stay closes modal only

- GIVEN the unsaved-changes modal is open
- WHEN the user clicks "Cancelar"
- THEN the modal closes and the user remains on the form with changes intact

#### Scenario: Escape key closes modal

- GIVEN the unsaved-changes modal is open
- WHEN the user presses Escape
- THEN the modal closes equivalent to clicking "Cancelar"

#### Scenario: Dirty flag resets on successful submit

- GIVEN a form marked as dirty
- WHEN the form is submitted successfully
- THEN the dirty flag is cleared

### Requirement: DESKTOP FORM CENTERING

On desktop viewports, narrow form cards MUST be horizontally centered to use available width efficiently.

#### Scenario: Form card centered at desktop breakpoint

- GIVEN a viewport width of 1024px or greater
- WHEN a form card with class `.form-card` is rendered
- THEN the card is horizontally centered with a maximum width of 520px

#### Scenario: Form card fills width on mobile

- GIVEN a viewport width below 1024px
- WHEN a form card with class `.form-card` is rendered
- THEN the card fills the available width without centering

### Requirement: ANSWER REORDER FETCH REDIRECT

When the answer reorder form is submitted, the system MUST intercept the POST, show a success toast, and redirect to the question detail page.

#### Scenario: Reorder success shows toast and redirects

- GIVEN a user reorders answers and submits the form
- WHEN the reorder POST succeeds
- THEN a success toast is displayed and the browser redirects to `/questions/{id}`

#### Scenario: Reorder failure leaves user on page

- GIVEN a user reorders answers and submits the form
- WHEN the reorder POST fails
- THEN an error toast is displayed and the user remains on the manage page

#### Scenario: Reorder degrades without JavaScript (REMOVED — false claim)

- GIVEN JavaScript is disabled
- WHEN the user submits the reorder form
- THEN the endpoint returns 422 because the form posts ``application/x-www-form-urlencoded`` with a JSON-string value while the server expects a JSON body (``ReorderRequest`` Pydantic model).  The no-JS path was already broken before this change; removing the degradation scenario documents reality: **answer reorder requires JavaScript**.
