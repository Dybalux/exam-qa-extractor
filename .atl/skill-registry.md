# Skill Registry

Generated: 2026-05-11
Project: image_to_text

## SDD Phase Skills

### sdd-explore
**Trigger**: Explore ideas before committing to a change  
**Path**: `~/.config/opencode/skills/sdd-explore/SKILL.md`

**Compact Rules**:
- Research and report back; only create exploration.md when tied to named change
- Load skills first (Section A from shared), then understand the request
- Investigate codebase, compare approaches, return structured analysis
- Save to `sdd/{change-name}/explore` (engram) or `openspec/changes/{change-name}/exploration.md`

### sdd-propose
**Trigger**: Create change proposal with intent, scope, and approach  
**Path**: `~/.config/opencode/skills/sdd-propose/SKILL.md`

**Compact Rules**:
- Read exploration (if exists) and project context first
- Create structured proposal.md with: title, motivation, success criteria
- Must include Capabilities section (New/Modified) for spec generation
- Save to `sdd/{change-name}/proposal` (engram) or `openspec/changes/{change-name}/proposal.md`

### sdd-spec
**Trigger**: Write delta specs with requirements and scenarios  
**Path**: `~/.config/opencode/skills/sdd-spec/SKILL.md`

**Compact Rules**:
- Read proposal first; specs must cover all capabilities listed
- New Capabilities → full specs; Modified Capabilities → delta specs
- Each spec needs: Requirements (MUST/SHOULD/MAY), Scenarios (GIVEN/WHEN/THEN)
- Concatenate multi-domain specs into single artifact for engram mode
- Save to `sdd/{change-name}/spec` (engram) or `openspec/changes/{change-name}/specs/{domain}/`

### sdd-design
**Trigger**: Create technical design and architecture approach  
**Path**: `~/.config/opencode/skills/sdd-design/SKILL.md`

**Compact Rules**:
- Read proposal (required) and spec (optional) before designing
- Read actual affected code to understand patterns and conventions
- Include: architecture decisions, data flow, file changes, technical rationale
- Save to `sdd/{change-name}/design` (engram) or `openspec/changes/{change-name}/design.md`

### sdd-tasks
**Trigger**: Break change into implementation tasks  
**Path**: `~/.config/opencode/skills/sdd-tasks/SKILL.md`

**Compact Rules**:
- Read proposal, spec, and design (all required) before task breakdown
- Organize tasks by phase (setup → core → polish → verify)
- Each task must be actionable: verb + subject + acceptance criteria
- Include Review Workload Forecast (line count, risk assessment)
- Save to `sdd/{change-name}/tasks` (engram) or `openspec/changes/{change-name}/tasks.md`

### sdd-apply
**Trigger**: Implement SDD tasks from specs and design  
**Path**: `~/.config/opencode/skills/sdd-apply/SKILL.md`

**Compact Rules**:
- Read proposal, spec, design, and tasks before writing ANY code
- Check Review Workload Forecast; apply chained-PR or exception rules
- Write minimal code to satisfy spec; prefer editing existing files
- Update tasks with `[x]` marks as completed; save progress artifact
- Save to `sdd/{change-name}/apply-progress` (engram) or update `openspec/changes/{change-name}/tasks.md`

### sdd-verify
**Trigger**: Execute tests and prove implementation matches specs  
**Path**: `~/.config/opencode/skills/sdd-verify/SKILL.md`

**Compact Rules**:
- Read all artifacts (proposal, spec, design, tasks) before judging
- Execute tests; static analysis alone is never verification
- Map each spec scenario to implementation evidence and test results
- If Strict TDD active, load `strict-tdd-verify.md` module
- Save to `sdd/{change-name}/verify-report` (engram) or `openspec/changes/{change-name}/verify-report.md`

### sdd-archive
**Trigger**: Archive completed change by syncing delta specs  
**Path**: `~/.config/opencode/skills/sdd-archive/SKILL.md`

**Compact Rules**:
- Read all artifacts (proposal, spec, design, tasks, verify-report)
- Merge delta specs into main specs for openspec/hybrid mode
- Move change folder to `openspec/changes/archive/` for openspec/hybrid
- Record all observation IDs in archive report for traceability
- Save to `sdd/{change-name}/archive-report` (engram) or `openspec/changes/archive/{change-name}/`

## Supporting Skills

### work-unit-commits
**Trigger**: Plan commits as reviewable work units  
**Path**: `~/.config/opencode/skills/work-unit-commits/SKILL.md`

**Compact Rules**:
- Commit by deliverable behavior, not by file type
- Keep tests with code they verify; keep docs with the feature
- Each commit tells a story; reviewer understands why from diff + message
- Apply to SDD tasks to avoid PRs above 400 changed lines

### branch-pr
**Trigger**: Create Gentle AI pull requests  
**Path**: `~/.config/opencode/skills/branch-pr/SKILL.md`

**Compact Rules**:
- Every PR MUST link an approved issue — no exceptions
- Every PR MUST have exactly one `type:*` label
- Automated checks must pass before merge possible
- Blank PRs without issue linkage blocked by GitHub Actions

### chained-pr
**Trigger**: Split oversized changes into chained PRs  
**Path**: `~/.config/opencode/skills/chained-pr/SKILL.md`

**Compact Rules**:
- Split PRs over 400 changed lines unless maintainer accepts `size:exception`
- Keep each PR reviewable in ≤60 minutes
- One deliverable work unit per PR; state dependencies and out-of-scope
- Child PRs include dependency diagram with current PR marked `📍`
- After 2 fix iterations with remaining issues, ask user to continue

### judgment-day
**Trigger**: Run blind dual review, fix confirmed issues, re-judge  
**Path**: `~/.config/opencode/skills/judgment-day/SKILL.md`

**Compact Rules**:
- Resolve project skills before launching agents; inject same standards to both judges
- Launch two blind judges in parallel; wait for both before synthesis
- Classify warnings: `WARNING (real)` only if normal use triggers; else INFO
- Ask before fixing Round 1 confirmed issues
- Re-launch both judges after any fix before commit/push/done
- Terminal states: `JUDGMENT: APPROVED` or `JUDGMENT: ESCALATED`

## Engram Naming Convention

All SDD artifacts follow deterministic naming:

```
title:     sdd/{change-name}/{artifact-type}
topic_key: sdd/{change-name}/{artifact-type}
type:      architecture
project:   image_to_text
scope:     project
```

### Artifact Types

| Type | Produced By | Description |
|------|-------------|-------------|
| `explore` | sdd-explore | Exploration analysis |
| `proposal` | sdd-propose | Change proposal |
| `spec` | sdd-spec | Delta specifications |
| `design` | sdd-design | Technical design |
| `tasks` | sdd-tasks | Task breakdown |
| `apply-progress` | sdd-apply | Implementation progress |
| `verify-report` | sdd-verify | Verification report |
| `archive-report` | sdd-archive | Archive closure |
| `state` | orchestrator | DAG state for recovery |

## Recovery Protocol

1. **Search**: `mem_search(query: "sdd/{change-name}/{artifact-type}", project: "image_to_text")`
2. **Retrieve**: `mem_get_observation(id: {observation-id})` for full content

---

*Registry auto-generated by sdd-init skill*
