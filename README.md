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

## Available Tools

| Category | Tools |
|----------|-------|
| **ASE** | Database management (`connect_or_create_db`, `store_result`, `query`, `get_atoms`, `list_databases`) |
| **Materials Project** | Material search, property data, synthesis recipes, detailed property data (`search_materials`, `get_material_properties`, `get_detailed_property_data`, `search_recipe`) |
| **PubChem** | Chemical compound search, properties, and safety data (`search_compounds`, `get_compound_properties`, `get_safety_data`) |
| **Pymatgen** | Structure generation: substitution, enumeration, defects, SQS, ion exchange, perturbation, prototypes (7 tools) |
| **Analysis** | Structure validation, composition analysis, structure analysis, stability analysis, structure fingerprinting (5 tools) |
| **ML Prediction** | Machine learning predictions for structure relaxation, band gap, and formation energy (`ml_relax_structure`, `ml_predict_bandgap`, `ml_predict_eform`) |
| **Selection** | Multi-objective ranking (Pareto, weighted sum, constraint-based) (`multi_objective_ranker`) |
| **Synthesis Planning** | Recipe quantification and template-based route generation (`synthesis_recipe_quantifier`, `template_route_generator`) |
| **URDF** | Validation, auto-fix, and inspection of Unified Robot Description Format files (`urdf_validate`, `urdf_fix`, `urdf_inspect`) |
| **Lula** | Generation of Lula robot description files for NVIDIA Isaac Sim (`lula_generate_robot_description`) |

## Available Skills

| Skill | Description |
|-------|-------------|
| **candidate-generator** | Integrated workflow for generating inorganic crystal structure candidates using pymatgen (substitution, enumeration, defects, SQS, perturbations) |
| **candidate-screener** | High-throughput screening workflow for filtering and enriching candidate structures with MP properties and stability analysis |
| **synthesis-planner** | Literature-first synthesis route planning workflow using Materials Project Synthesis Explorer with template-based fallback |
| **vasp-ase** | Professional workflow for setting up, executing, and debugging VASP DFT calculations using ASE |
| **urdf-validator** | Pre-import validation and auto-fix workflow for URDF files targeting Isaac Sim |
| **lula-description-generator** | Workflow for generating Lula robot descriptions with automatic collision sphere placement for NVIDIA Isaac Sim |
| **nsys-optimizer** | Performance profiling and optimization for computational workflows using NVIDIA Nsight Systems |

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
