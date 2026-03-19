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
│  (orchestrate multiple tools)           │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│           MCP Server                    │  ← Exposes tools via MCP
│   ┌─────────────────────────────────┐   │
│   │  Tools:                         │   │
│   │  • ASE (database operations)    │   │
│   │  • Materials Project (queries)  │   │
│   │  • PubChem (chemical search)    │   │
│   │  • Pymatgen (structure gen)     │   │
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
| **ASE** | Database management, structure storage/retrieval, property queries |
| **Materials Project** | Material search, property data, synthesis recipes |
| **PubChem** | Chemical compound search and properties |
| **Pymatgen** | Structure generation (substitution, enumeration, defects, SQS, ion exchange, perturbation, prototypes) |

## Available Skills

| Skill | Description |
|-------|-------------|
| **candidate-generator** | Integrated workflow for generating inorganic crystal structure candidates for high-throughput screening |
| **nsys-optimizer** | Performance profiling and optimization for computational workflows |

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
