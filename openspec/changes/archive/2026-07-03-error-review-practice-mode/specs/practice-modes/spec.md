# Practice Modes Specification

## Purpose

Define the available practice session modes, their question-selection behavior, and the user-facing controls for starting a practice session.

## Requirements

### Requirement: REQ-PM-1 (Practice Mode Enumeration)

The system SHALL support exactly these practice modes, each identified by a unique string value:

| Mode | Value | Description |
|------|-------|-------------|
| Random | `random` | Questions drawn uniformly from the full pool |
| By Partial | `by_partial` | Questions restricted to a specific exam |
| By Topic | `by_topic` | Questions restricted to a specific topic |
| Exam Simulation | `exam_simulation` | Questions matching a real exam's structure |
| Error Review | `error_review` | Questions the user has previously answered incorrectly |

#### Scenario: Mode value is validated on session creation

- GIVEN a request to create a practice session
- WHEN the `mode` field does not match one of the five enumerated values
- THEN the system MUST reject the request with a validation error listing valid modes

#### Scenario: Error review mode is accepted as a valid mode

- GIVEN a request with `mode = "error_review"`
- WHEN the request is validated
- THEN the mode MUST pass validation without error

### Requirement: REQ-PM-2 (Error Review Question Selection)

When mode is `error_review`, the system MUST restrict the available question pool to questions the user has previously answered with `is_correct = False` in any prior practice session.

#### Scenario: Error review returns only previously-failed questions

- GIVEN a user has answered questions Q1 (incorrect), Q2 (correct), Q3 (incorrect) across past sessions
- WHEN the user starts an error review session
- THEN the available pool MUST include Q1 and Q3, and MUST NOT include Q2

#### Scenario: Error review respects exam filter

- GIVEN a user has failed questions across exams E1 and E2
- WHEN the user starts an error review session with `exam_id = E1`
- THEN the available pool MUST include only failed questions belonging to E1

#### Scenario: Error review respects topic filter

- GIVEN a user has failed questions on topics "memory" and "processes"
- WHEN the user starts an error review session with `topic = "memory"`
- THEN the available pool MUST include only failed questions on topic "memory"

#### Scenario: Error review deduplicates by question ID

- GIVEN a user has answered question Q1 incorrectly in three separate sessions
- WHEN the system builds the error review pool
- THEN Q1 MUST appear exactly once in the pool

### Requirement: REQ-PM-3 (Empty Error Pool Handling)

When mode is `error_review` and the user has no previously failed questions matching the selected filters, the system MUST raise a `ValidationError` with a user-facing message.

#### Scenario: No failed questions at all

- GIVEN a user has never answered any question incorrectly
- WHEN the user attempts to start an error review session
- THEN the system MUST raise a `ValidationError`
- AND the user MUST see the flash message: "Todavía no tenés errores para revisar."

#### Scenario: No failed questions matching filters

- GIVEN a user has only failed questions on topic "memory"
- WHEN the user attempts to start an error review session with `topic = "processes"`
- THEN the system MUST raise a `ValidationError`
- AND the user MUST see a flash message indicating no matching errors were found

### Requirement: REQ-PM-4 (Database Constraint)

The `practice_sessions` table MUST enforce a `CheckConstraint` on the `mode` column that includes all valid mode values.

#### Scenario: Constraint includes error_review

- GIVEN the database schema is migrated
- WHEN inserting a row with `mode = 'error_review'`
- THEN the insert MUST succeed without constraint violation

#### Scenario: Constraint rejects invalid mode

- GIVEN the database schema is migrated
- WHEN inserting a row with `mode = 'invalid_mode'`
- THEN the insert MUST fail with a constraint violation

### Requirement: REQ-PM-5 (Frontend Mode Selection)

The practice start page MUST present all available practice modes as selectable radio options, each with a label and descriptive subtitle.

#### Scenario: Error review option is visible on start page

- GIVEN a user navigates to `/practice`
- WHEN the page renders
- THEN a radio option for "Error Review" MUST be present
- AND it MUST display the subtitle: "Preguntas que alguna vez respondiste mal"

#### Scenario: Validation error redirects with flash message

- GIVEN a user selects error review mode with no failed questions
- WHEN the form is submitted
- THEN the user MUST be redirected back to `/practice`
- AND a flash message MUST be displayed explaining no errors are available

### Requirement: REQ-PM-6 (Integration with Existing Practice Flow)

Error review mode MUST integrate with the existing practice session lifecycle without modifying the behavior of other modes.

#### Scenario: Error review session follows standard lifecycle

- GIVEN an error review session is created successfully
- WHEN the user answers questions, skips, and completes the session
- THEN the session MUST behave identically to other modes: tracking accuracy, time, and responses

#### Scenario: Existing modes are unaffected

- GIVEN the error review mode is added
- WHEN a user starts a session in `random`, `by_partial`, `by_topic`, or `exam_simulation` mode
- THEN the question selection and session behavior MUST be unchanged from prior behavior
