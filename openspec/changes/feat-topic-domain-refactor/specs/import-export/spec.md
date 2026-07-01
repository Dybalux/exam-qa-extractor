## Domain: import-export (Modified Capability)

### Purpose
Support legacy JSON v1.0 imports by dynamically resolving/creating missing topics under the default subject.

### Requirements

#### Requirement: REQ-IMP-1 (Legacy Schema Parsing)
The import service MUST accept and parse legacy JSON v1.0 export files, mapping raw topic strings to database entities.
(Previously: Imports expected all topics to match existing pre-defined static enums.)

##### Scenario: Import Legacy JSON with Existing Topic
- GIVEN a legacy JSON v1.0 export file containing a question with topic "Procesos"
- WHEN the import service processes the file
- THEN the question MUST be matched to the existing Topic slugged "procesos"

#### Requirement: REQ-IMP-2 (Dynamic Topic Resolution on Import)
If a legacy import contains an unrecognized topic string, the service MUST dynamically create a new Topic record under the default Subject.
(Previously: Imports with unrecognized topic strings failed validation.)

##### Scenario: Import Legacy JSON with Missing Topic
- GIVEN a legacy JSON v1.0 export containing a question with unrecognized topic "Virtual Memory"
- WHEN the import service processes the file
- THEN the service MUST dynamically create a new Topic record with slug "virtual-memory" under the default Subject and link the question to it
