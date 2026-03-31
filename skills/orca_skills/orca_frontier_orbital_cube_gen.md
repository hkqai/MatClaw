---
name: ORCA Frontier Orbital Cube Gen
description: Safely prepare HOMO and LUMO cube files for visualization using guarded environment and directory preflight checks.
tools:
  - validate_environment
  - validate_orca_calc_dir
  - generate_homo_lumo_cubes
---

# ORCA Frontier Orbital Cube Gen

This skill prepares **HOMO and LUMO cube files** for visualization from an ORCA calculation directory.

It is a guarded workflow, not a blind tool wrapper.  
Its purpose is to reduce mistakes caused by:

- missing environment dependencies
- ambiguous `.out` / `.gbw` file selection
- unwritable directories
- open-shell orbital interpretation risks
- version-sensitive `orca_plot` behavior

## Primary Goal

Generate:

- HOMO cube file
- LUMO cube file

while also producing a clear reliability assessment.

---

## When to Use

Use this skill when:

- the user wants frontier-orbital visualization artifacts
- the workflow has a calculation directory, not just a single output file
- HOMO/LUMO cube generation should be done conservatively

Do **not** use this skill when:

- the environment has not been checked and cube generation is known to be impossible
- the task is only to summarize an ORCA output file
- the workflow requires a specific orbital number rather than HOMO/LUMO

---

## Required Input

- `calc_dir`: calculation directory
- `preference`: one of:
  - `optimization`
  - `single_point`
  - `auto`
- `ngrid`: grid intervals string, e.g. `80 80 80`
- `operator`: spin operator index
  - `0` for alpha or closed-shell
  - `1` for beta
- optional policy flag:
  - `allow_risky_ambiguity`: boolean

---

## Tools to Call

Use these tools in order:

1. `validate_environment(test_dir=calc_dir)`
2. `validate_orca_calc_dir(calc_dir)`
3. `generate_homo_lumo_cubes(calc_dir, preference, ngrid, operator)`

Do not skip preflight checks in normal MCP execution.

---

## Workflow

1. Perform environment validation.
2. Perform directory validation.
3. Decide whether cube generation should proceed.
4. If the directory is not cube-ready, stop.
5. If the directory requires manual review and `allow_risky_ambiguity` is false, stop.
6. Otherwise call `generate_homo_lumo_cubes(...)`.
7. Collect:
   - selected output file
   - orbital information
   - generated HOMO cube path
   - generated LUMO cube path
8. Interpret warnings and produce a task-level result.

---

## Stop Conditions

Stop and return failure if any of the following apply:

- environment is not ready for cube generation
- directory validation fails
- directory is not writable
- no `.out` file exists
- no `.gbw` file exists
- triage indicates manual review is needed and `allow_risky_ambiguity` is false
- `generate_homo_lumo_cubes` fails

---

## How to Interpret Warnings

Warnings are scientifically meaningful in this workflow.

### High-importance examples

- open-shell markers  
  → HOMO/LUMO assignment may require manual verification

- ambiguous `.out` selection  
  → the chosen calculation may not be the intended one

- low-confidence `.gbw` match  
  → generated cube may not correspond to the intended output

- `orca_plot` menu incompatibility signals  
  → generated files may be missing or inconsistent

### Response Rule

If warnings exist:

- report cube paths if generation succeeded
- clearly state reduced confidence
- do not claim frontier orbital assignment is definitive

---

## Output Requirements

Return a structured response containing:

- `skill`: `"ORCA Frontier Orbital Cube Gen"`
- `success`
- `status`
- `summary`
- `key_findings`
- `reliability_notes`
- `recommended_next_step`
- `artifacts`
- `tool_trace`

Artifacts should include:

- `calc_dir`
- `selected_out_file`
- `homo_cube`
- `lumo_cube`
- `orbital_info`
- `ngrid`
- `operator`

---

## Example Output Shape

```json
{
  "skill": "ORCA Frontier Orbital Cube Gen",
  "success": true,
  "status": "success_with_warnings",
  "summary": "HOMO/LUMO cube files were generated successfully for the selected ORCA calculation.",
  "key_findings": [
    "Selected ORCA output: /path/job_opt.out",
    "HOMO orbital number: 25",
    "LUMO orbital number: 26",
    "Grid used: 80 80 80",
    "Spin operator used: 0"
  ],
  "reliability_notes": [
    "Open-shell markers detected; frontier orbital interpretation may require manual review."
  ],
  "recommended_next_step": "Use these cubes for visualization only with the reported orbital-assignment caution.",
  "artifacts": {
    "homo_cube": "/path/job.HOMO.mo25a.ngrid808080.cube",
    "lumo_cube": "/path/job.LUMO.mo26a.ngrid808080.cube"
  },
  "tool_trace": {
    "validate_environment": {},
    "validate_orca_calc_dir": {},
    "generate_homo_lumo_cubes": {}
  }
}
