---
name: ORCA Output Summarizer
description: Summarize a single ORCA output file into convergence, energy, orbital, and frequency findings with reliability notes.
tools:
  - summarize_orca_output
---

# ORCA Output Summarizer

This skill summarizes a **single ORCA `.out` file** into a structured scientific overview suitable for MCP-driven workflows.

Use this skill when the workflow already knows which ORCA output file should be analyzed and the goal is to extract the most important result information in one pass.

## Primary Goal

Produce a task-oriented summary of:

- convergence and normal termination
- final single-point energy
- HOMO/LUMO indices and energies
- HOMO-LUMO gap
- imaginary frequency count
- reliability notes based on parser warnings

---

## When to Use

Use this skill when:

- the user provides a specific ORCA `.out` file
- the workflow needs a concise but structured interpretation
- the workflow wants a stable, general-purpose ORCA summary entry point

Do **not** use this skill when:

- the user provides only a directory and the correct `.out` file is not known
- the workflow’s main task is cube generation
- the workflow needs batch summary of many outputs

---

## Required Input

- `out_file`: path to a single ORCA `.out` file

Input assumptions:

- the path should point to a readable file
- the file should be an ORCA output or at least resemble one
- the file may still contain parser ambiguities or scientific caveats

---

## Tool to Call

Call the following tool:

- `summarize_orca_output(out_file)`

Do not manually reimplement its internal sub-steps unless debugging is explicitly required.

---

## Workflow

1. Call `summarize_orca_output(out_file)`.
2. If the tool fails:
   - report the failure clearly
   - include the main failure reason
   - do not fabricate scientific values
3. If the tool succeeds:
   - extract major findings from:
     - `convergence`
     - `final_energy`
     - `orbital_energies`
     - `frequency_analysis`
4. Collect and interpret `warnings`.
5. Present results as:
   - concise overall summary
   - key findings
   - reliability notes
   - recommended next step

---

## How to Interpret Warnings

Treat warnings as reliability signals, not cosmetic text.

### High-importance examples

- open-shell or spin-channel warnings  
  → frontier orbital interpretation may require manual review

- missing `HURRAY` in an optimization-like output  
  → do not present optimization as confidently converged

- no obvious frequency markers  
  → do not overstate the meaning of zero imaginary frequencies

- multiple orbital blocks  
  → HOMO/LUMO parsing may be heuristic

### Response Rule

If warnings exist:

- still report parsed values if they were successfully extracted
- clearly downgrade confidence where appropriate
- do not state uncertain results as definitive

---

## Output Requirements

Return a structured response containing:

- `skill`: `"ORCA Output Summarizer"`
- `success`: boolean
- `status`: `"success"`, `"success_with_warnings"`, or `"failed"`
- `summary`: concise task-level summary
- `key_findings`: list of factual findings
- `reliability_notes`: list of warning interpretations
- `recommended_next_step`: short action-oriented recommendation
- `artifacts`: extracted values and key paths
- `tool_trace`: raw result from `summarize_orca_output`

---

## Stop Conditions

Stop and return failure if:

- the file does not exist
- the file cannot be read
- the summary tool returns failure
- parsing fails badly enough that no reliable summary can be formed

Do not invent missing values.

---

## Example Output Shape

```json
{
  "skill": "ORCA Output Summarizer",
  "success": true,
  "status": "success_with_warnings",
  "summary": "ORCA output was summarized successfully, but the result requires caution based on parser warnings.",
  "key_findings": [
    "Normal termination detected: true",
    "Inferred job type: optimization",
    "Final single-point energy (Hartree): -1234.56789",
    "HOMO-LUMO gap (eV): 3.33",
    "Imaginary frequency count: 0"
  ],
  "reliability_notes": [
    "Open-shell markers detected; frontier orbital interpretation may require manual review."
  ],
  "recommended_next_step": "Review warning context before using frontier orbital values as final conclusions.",
  "artifacts": {
    "input_out_file": "/path/job.out",
    "energy_hartree": -1234.56789
  },
  "tool_trace": {
    "summarize_orca_output": {}
  }
}
