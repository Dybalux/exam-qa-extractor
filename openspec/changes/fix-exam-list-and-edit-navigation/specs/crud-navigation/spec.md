# CRUD Navigation Specification

## Purpose

Define post-save redirect targets and cancel-link destinations for all CRUD entities (exams, questions, answers, images) to ensure predictable navigation after mutations.

## Requirements

### Requirement: POST-SAVE REDIRECT

After a successful create or edit mutation, the system MUST redirect to a list page for entities that have one, or to the parent detail page for child entities. Flash messages MUST be included via query parameters.

#### Scenario: Exam create redirects to exam list

- GIVEN a user submits a valid exam creation form
- WHEN the exam is persisted successfully
- THEN the system redirects to `/exams` with a flash message "Examen guardado"

#### Scenario: Exam edit redirects to exam list

- GIVEN a user submits a valid exam edit form
- WHEN the exam is updated successfully
- THEN the system redirects to `/exams` with a flash message "Examen guardado"

#### Scenario: Manual question create redirects to question list

- GIVEN a user submits a valid manual question creation form
- WHEN the question is persisted successfully
- THEN the system redirects to `/questions` with a flash message "Pregunta guardada"

#### Scenario: OCR correction redirects to question list

- GIVEN a user submits a valid OCR correction form
- WHEN the correction is persisted successfully
- THEN the system redirects to `/questions` with a flash message "Corrección guardada"

#### Scenario: Answer create/edit redirects to parent question detail

- GIVEN a user submits a valid answer create or edit form
- WHEN the answer is persisted successfully
- THEN the system redirects to `/questions/{qid}` (no answer list exists)

#### Scenario: Image upload redirects contextually

- GIVEN a user submits a valid image upload form
- WHEN the upload is processed successfully
- THEN the system redirects to the context-aware destination (review queue or exam detail) with a flash message

#### Scenario: Image upload preserves return_to via hidden input

- GIVEN an image upload form includes a hidden `return_to` input
- WHEN the upload completes
- THEN the redirect destination respects the `return_to` value if present

### Requirement: CANCEL LINK TARGET

Cancel links on CRUD forms MUST navigate to a predictable, explicit URL — never to `history.back()` or inconsistent targets.

#### Scenario: Exam edit cancel navigates to exam list

- GIVEN a user is editing an existing exam
- WHEN the user clicks Cancel
- THEN the browser navigates to `/exams`

#### Scenario: Manual question create cancel navigates to question list

- GIVEN a user is creating a question manually
- WHEN the user clicks Cancel
- THEN the browser navigates to `/questions`

#### Scenario: OCR correction cancel navigates to question list

- GIVEN a user is correcting an OCR question
- WHEN the user clicks Cancel
- THEN the browser navigates to `/questions` (not `history.back()`)

#### Scenario: Answer form cancel navigates to parent question detail

- GIVEN a user is creating or editing an answer
- WHEN the user clicks Cancel
- THEN the browser navigates to `/questions/{qid}`

#### Scenario: Bulk upload cancel navigates to exam detail

- GIVEN a user is on the bulk upload page for an exam
- WHEN the user clicks Cancel
- THEN the browser navigates to `/exams/{id}`
