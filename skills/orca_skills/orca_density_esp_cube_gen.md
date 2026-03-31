---
name: ORCA Density/ESP Cube Gen
description: Safely prepare matched electron-density and electrostatic-potential cube files for visualization, including grid-consistency validation.
tools:
  - validate_environment
  - validate_orca_calc_dir
  - generate_density_and_esp_cubes
---

# ORCA Density/ESP Cube Gen

This skill prepares a matched pair of:

- electron-density cube
- electrostatic-potential cube

for downstream visualization workflows.

This is a guarded workflow designed to reduce common failures such as:

- missing `orca_plot`
- unwritable directories
- ambiguous `.gbw` selection
- unexpected output naming
- density and ESP cubes that do not share the same grid

## Primary Goal

Generate a matched density/ESP cube pair and confirm that the two cubes are suitable to use together.

---

## When to Use

Use this skill when:

- the user wants ESP mapping or related visualization
- the workflow needs electron density and ESP on a common grid
- a calculation directory is available

Do **not** use this skill when:

- only ORCA output parsing is needed
- the workflow requires arbitrary single cube generation unrelated to density/ESP pairing

---

## Required Input

- `calc_dir`: calculation directory
- `preference`: one of:
  - `optimization`
  - `single_point`
  - `auto`
- `ngrid`: grid intervals string, e.g. `80 80 80`
- optional policy flag:
  - `allow_risky_ambiguity`: boolean

---

## Tools to Call

Use these tools in order:

1. `validate_environment(test_dir=calc_dir)`
2. `validate_orca_calc_dir(calc_dir)`
3. `generate_density_and_esp_cubes(calc_dir, preference, ngrid)`

Do not bypass preflight checks during standard MCP execution.

---

## Workflow

1. Validate environment readiness.
2. Validate calculation-directory readiness.
3. If the directory is not cube-ready, stop.
4. If manual review is recommended and `allow_risky_ambiguity` is false, stop.
5. Otherwise call `generate_density_and_esp_cubes(...)`.
6. Inspect returned validation information, especially grid consistency.
7. Produce a task-level result with:
   - selected output file
   - selected GBW file
   - density cube path
   - ESP cube path
   - grid consistency interpretation

---

## Stop Conditions

Stop and return failure if:

- environment is not ready
- directory validation fails
- directory is not writable
- required `.out` or `.gbw` files are missing
- triage recommends manual review and `allow_risky_ambiguity` is false
- density/ESP generation fails
- density and ESP cubes do not share a valid consistent grid

---

## How to Interpret Warnings

Warnings in this workflow can affect visualization correctness.

### High-importance examples

- ambiguous `.gbw` selection  
  → density and ESP may come from the wrong wavefunction

- output naming ambiguity  
  → discovered cube files may need manual confirmation

- `orca_plot` incompatibility  
  → expected cube outputs may not be trustworthy

- grid consistency problems  
  → the density and ESP cubes should not be treated as a valid matched pair

### Response Rule

If warnings exist:

- still report generated file paths if generation succeeded
- clearly state whether the pair is validated for joint use
- do not treat a non-validated pair as visualization-ready

---

## Output Requirements

Return a structured response containing:

- `skill`: `"ORCA Density/ESP Cube Gen"`
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
- `gbw_file`
- `electron_density_cube`
- `electrostatic_potential_cube`
- `validation_result`
- `ngrid`

---

## Example Output Shape

```json
{
  "skill": "ORCA Density/ESP Cube Gen",
  "success": true,
  "status": "success",
  "summary": "Electron-density and ESP cube files were generated successfully and validated to share the same grid.",
  "key_findings": [
    "Selected ORCA output: /path/job_opt.out",
    "Selected GBW file: /path/job_opt.gbw",
    "Density/ESP grid consistency: true"
  ],
  "reliability_notes": [
    "No major density/ESP workflow warnings were produced."
  ],
  "recommended_next_step": "These matched cube files are ready for visualization workflows that require a shared grid.",
  "artifacts": {
    "electron_density_cube": "/path/job_opt.eldens.ngrid808080.cube",
    "electrostatic_potential_cube": "/path/job_opt.scfp.esp.ngrid808080.cube"
  },
  "tool_trace": {
    "validate_environment": {},
    "validate_orca_calc_dir": {},
    "generate_density_and_esp_cubes": {}
  }
}
