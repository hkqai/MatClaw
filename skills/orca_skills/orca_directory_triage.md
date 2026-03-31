---
name: ORCA Directory Triage
description: Assess whether an ORCA calculation directory is ready for analysis or cube-generation workflows.
tools:
  - validate_environment
  - validate_orca_calc_dir
---

# ORCA Directory Triage

This skill acts as a **workflow gatekeeper** for ORCA calculation directories.

Use it to determine whether a directory is suitable for:

- ORCA result analysis
- HOMO/LUMO cube generation
- density/ESP cube generation

This skill is especially useful before any workflow that depends on `.out`, `.gbw`, directory writability, or `orca_plot`.

## Primary Goal

Produce a structured readiness assessment with these judgments:

- `summary_ready`
- `cube_ready`
- `manual_review_recommended`

---

## When to Use

Use this skill when:

- the user provides a calculation directory instead of a single `.out` file
- the workflow must decide whether to continue automatically
- cube generation may be requested next
- the environment and directory state are not yet trusted

Do **not** use this skill when:

- the workflow already has a validated single `.out` file and only needs analysis
- the task is batch summary of many unrelated directories

---

## Required Input

- `calc_dir`: path to a calculation directory

Input assumptions:

- the directory may contain `.out` and `.gbw` files
- the directory may contain multiple candidates and require caution
- the directory may not be writable

---

## Tools to Call

Call these tools:

1. `validate_environment(test_dir=calc_dir)`
2. `validate_orca_calc_dir(calc_dir)`

Use both results together to determine readiness.

---

## Workflow

1. Call `validate_environment(test_dir=calc_dir)`.
2. Call `validate_orca_calc_dir(calc_dir)`.
3. Combine findings into workflow-level judgments:
   - `summary_ready`
   - `cube_ready`
   - `manual_review_recommended`
4. Interpret warnings instead of forwarding them blindly.
5. Produce a task-level summary explaining whether the directory is ready and why.

---

## Readiness Logic

### `summary_ready`
Set to true only if:

- directory validation succeeded
- at least one `.out` file exists

### `cube_ready`
Set to true only if all of the following are true:

- environment validation succeeded
- directory validation succeeded
- directory is writable
- at least one `.out` file exists
- at least one `.gbw` file exists

### `manual_review_recommended`
Set to true if any of the following occur:

- multiple `.out` files
- multiple `.gbw` files
- no same-stem `.out/.gbw` pair
- environment ambiguity
- warning patterns that imply reduced confidence

---

## How to Interpret Warnings

Treat warnings as workflow risk signals.

### Examples

- multiple `.out` files  
  → automatic selection may be ambiguous

- multiple `.gbw` files  
  → cube-generation file matching may be unreliable

- no same-stem pair  
  → matching may fall back to heuristic behavior

- directory not writable  
  → cube generation should not proceed

- `orca_plot` not found  
  → analysis may still be possible, cube generation should stop

---

## Output Requirements

Return a structured response containing:

- `skill`: `"ORCA Directory Triage"`
- `success`: boolean
- `status`
- `summary`
- `key_findings`
- `reliability_notes`
- `recommended_next_step`
- `artifacts`
- `tool_trace`

Artifacts should include at least:

- `calc_dir`
- `summary_ready`
- `cube_ready`
- `manual_review_recommended`
- counts of `.out` and `.gbw`
- `same_stem_pairs` if available

---

## Stop Conditions

Return failure if:

- the directory does not exist
- the directory cannot be validated at all

Do not claim cube readiness if:

- `orca_plot` is unavailable
- the directory is not writable
- no `.gbw` files exist

---

## Example Output Shape

```json
{
  "skill": "ORCA Directory Triage",
  "success": true,
  "status": "success_with_warnings",
  "summary": "The calculation directory is usable for analysis, but cube-generation readiness is limited or requires caution.",
  "key_findings": [
    "ORCA output files found: 2",
    "GBW files found: 1",
    "Directory writable: true",
    "Summary-ready: true",
    "Cube-ready: true",
    "Manual review recommended: true"
  ],
  "reliability_notes": [
    "Multiple .out files detected; automatic selection may be ambiguous."
  ],
  "recommended_next_step": "Review output-file ambiguity before starting cube generation.",
  "artifacts": {
    "calc_dir": "/path/calc",
    "summary_ready": true,
    "cube_ready": true,
    "manual_review_recommended": true
  },
  "tool_trace": {
    "validate_environment": {},
    "validate_orca_calc_dir": {}
  }
}
