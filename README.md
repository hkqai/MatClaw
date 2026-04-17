# MatClaw

**Agent tools and skills for autonomous materials research**

MatClaw is a library of specialized tools and skills designed for AI agents working in computational materials discovery. It provides capabilities across the full materials research lifecycle—from candidate generation and simulation to active learning and experiment planning.

## Architecture

MatClaw follows a layered architecture:

```
┌─────────────────────────────────────────┐
│              AI Agents                  │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│              Skills                     │  ← High-level workflows
│     (orchestrate multiple tools)        │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│             MCP Server                  │  ← Exposes tools via MCP
│   ┌─────────────────────────────────┐   │
│   │           Tools                 │   │
│   └─────────────────────────────────┘   │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│    External Services & Libraries        │
└─────────────────────────────────────────┘
```

**Tools** are implemented within the MCP server and provide atomic operations. **Skills** are agent workflows that call multiple tools through the MCP protocol to accomplish complex research tasks.

## Available Skills

| Skill | Description |
|-------|-------------|
| **urdf-validator** | Validate and auto-fix URDF robot models for Isaac Sim / USD compatibility |
| **lula-description-generator** | Generate Lula robot descriptions with collision-sphere placement for NVIDIA Isaac Sim |
| **isaac-lab-scene-init** | Initialize robot scenes in NVIDIA Isaac Lab |
| **candidate-generator** | Generate candidate materials using pymatgen structure manipulation tools |
| **candidate-screener** | Screen candidate materials using ML prediction and stability analysis |
| **vasp-ase** | VASP DFT calculations using ASE interface |
| **orca_skills** | Quantum chemistry workflows: density/ESP cube generation, frontier orbital analysis, output summarization, directory triage |
| **synthesis-planner** | Intelligent synthesis route planning - always tries literature search (Materials Project) first, falls back to template-based routes only when no literature data exists |
| **active-learning** | Autonomous synthesis optimization using ARROWS with automated XRD characterization |
| **nsys-optimizer** | Profile and optimize CUDA/GPU code using NVIDIA Nsight Systems |

## Available Tools

| Category | Tools |
|----------|-------|
| **URDF** | Robot model validation and fixing for Isaac Sim/USD compatibility (`urdf_validate`, `urdf_fix`, `urdf_inspect`) |
| **Lula** | Generate Lula robot descriptions with automated collision-sphere placement for Isaac Sim motion planning (`lula_generate_robot_description`) |
| **ASE** | Database management (`connect_or_create_db`, `store_result`, `query`, `get_atoms`, `list_databases`) |
| **Materials Project** | Material search, property data, synthesis recipes, detailed property data (`search_materials`, `get_material_properties`, `get_detailed_property_data`, `search_recipe`) |
| **PubChem** | Chemical compound search, properties, and safety data (`search_compounds`, `get_compound_properties`, `get_safety_data`) |
| **Composition Generation** | Enumerate charge-balanced chemical compositions from element lists with oxidation states (`composition_enumerator`) |
| **Pymatgen** | Structure generation: substitution, enumeration, defects, SQS, ion exchange, perturbation, prototypes (7 tools) |
| **Analysis** | Structure validation, composition analysis, structure analysis, stability analysis, structure fingerprinting (5 tools) |
| **ML Prediction** | Machine learning predictions for structure relaxation, band gap, and formation energy (`ml_relax_structure`, `ml_predict_bandgap`, `ml_predict_eform`) |
| **ChemLLM** | Molecule binding and synthesizability prediction using fine-tuned LLMs (`predict_molecule_binding`, `predict_molecule_synthesizability`) |
| **Selection** | Multi-objective ranking (Pareto, weighted sum, constraint-based) (`multi_objective_ranker`) |
| **ORCA** | Quantum chemistry output analysis and cube file generation (`orca_analysis_tools`, `orca_cube_tools`) |
| **Synthesis Planning** | Recipe quantification and template-based route generation (`synthesis_recipe_quantifier`, `template_route_generator`) |
| **ElemwiseRetro** | Synthesis recipe prediction for inorganic solid state synthesis (`er_predict_precursors`, `er_predict_temperature`) |
| **ARROWS** | Campaign management for synthesis active learning through ARROWS (`arrows_initialize_campaign`, `arrows_suggest_experiment`, `arrows_record_result`) |
| **Bayesian Optimization** | Campaign management for synthesis active learning through Bayesian Optimization (`bo_initialize_campaign`, `bo_suggest_experiment`, `bo_record_result`) |
| **Characterization** | Automated phase identification from powder diffraction patterns using deep learning (`xrd_analyze_pattern`) |
| **Image Retrieval** | Scientific paper figure extraction, image segmentation, SEM classification (`paper_image_extract`, `image_segmentation`, `sem_image_classification`) |


## Setup

```bash
cd mcp
./setup.sh
```

The setup script will install dependencies and configure the MCP server.

## Usage

Start the MCP server:
```bash
cd mcp
python server.py
```

Skills can then reference the exposed tools for autonomous agent workflows.

## Development Status

⚠️ **This project is under active development.** APIs and workflows may change.

## License

See [LICENSE](LICENSE) for details.
