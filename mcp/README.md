# MatClaw MCP Server

MCP (Model Context Protocol) server exposing tools for inorganic materials discovery: PubChem, Materials Project, ASE, and pymatgen-based structure generators.

---

## Quick start

```bash
cd mcp/
bash setup.sh
source venv/bin/activate
python server.py
```

---

## Dependencies

The server has two kinds of dependencies:

| Dependency | Install via | Required for |
|---|---|---|
| Python packages (mcp, pymatgen, ase, …) | `pip` / `requirements.txt` | All tools |
| `enum.x` (enumlib) | `conda` (Linux/macOS/WSL only) | `pymatgen_enumeration_generator` only |

All pip packages are installed automatically by `setup.sh`. The `setup.sh` script also attempts to install `enumlib` via conda if conda is available.

### Why two package managers?

`enumlib` is a compiled C++ binary (`enum.x`) that implements the Hart-Forcade enumeration algorithm. It is:

- **Not on PyPI** — `pip install enumlib` will fail.
- **Only on conda-forge for Linux and macOS** — Windows requires WSL.

All other tools work with pip only. `pymatgen_enumeration_generator` is the sole tool that needs `enum.x`.

---

## Installation

### Linux / macOS (recommended)

```bash
cd mcp/

# Full setup — creates venv, installs pip packages, installs enumlib via conda
bash setup.sh

# Activate the venv
source venv/bin/activate
```

If conda is not installed, the script will skip enumlib and warn you. Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) first if you need enumeration support.

### Windows (native)

Native Windows supports all tools **except** `pymatgen_enumeration_generator` because `enum.x` is not available for Windows.

```powershell
cd mcp\

# Create and activate the venv
python -m venv venv
venv\Scripts\activate

# Install pip dependencies
pip install -r requirements.txt

# Copy the env file
copy .env.example .env
```

### Windows + WSL (full support)

WSL provides a Linux environment where `enumlib` can be installed normally.

**One-time WSL setup** (run in PowerShell as Administrator):
```powershell
wsl --install -d Ubuntu
# Restart Windows when prompted
```

**Inside the Ubuntu WSL terminal:**
```bash
# Install Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh
bash ~/miniconda.sh -b -p ~/miniconda3
~/miniconda3/bin/conda init bash
source ~/.bashrc

# Run the full setup script (your project is mounted at /mnt/c/...)
cd "/mnt/c/Users/<your-user>/Documents/Projects/Project 1-3/Code/MatClaw/mcp"
# Fix Windows line endings so bash can run the script
sed -i 's/\r//' setup.sh
bash setup.sh
source venv/bin/activate
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your API keys:

```dotenv
MP_API_KEY="your_materials_project_api_key_here"
```

Get a free Materials Project API key at [materialsproject.org](https://materialsproject.org/api).

---

## Running the server
Linux/macOS/WSL:
```bash
source venv/bin/activate
python server.py
```

Windows:
```bash
venv\Scripts\activate
python server.py
```
---

## Running tests

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

Tests for `pymatgen_enumeration_generator` that require `enum.x` are automatically **skipped** when `enum.x` is not on PATH. This is expected on Windows without WSL.

```
# Expected on Windows without WSL
6 passed, 28 skipped   ← correct, not a failure

# Expected on Linux/macOS/WSL with enumlib installed
34 passed, 0 skipped
```

Run only the enumeration tests:
```bash
python -m pytest tests/pymatgen/test_enumeration_generator.py -v
```

---

## Tools

| Tool | Description |
|---|---|
| `pubchem_search_compounds` | Search PubChem by name, SMILES, formula, InChIKey |
| `pubchem_get_compound_properties` | Get detailed properties for PubChem CIDs |
| `mp_search_materials` | Search Materials Project for inorganic crystals |
| `mp_get_material_properties` | Get detailed properties for MP material IDs |
| `mp_get_detailed_property_data` | Get band structure, DOS, elastic tensor, etc. |
| `mp_search_recipe` | Search Synthesis Explorer for experimental recipes |
| `ase_connect_or_create_db` | Connect to or create an ASE SQLite database |
| `ase_store_result` | Store an Atoms object and results to the database |
| `ase_query_db` | Query the ASE database by formula, property, tag |
| `ase_get_atoms` | Retrieve full Atoms objects from the database |
| `ase_list_databases` | List and summarize ASE .db files in a directory |
| `pymatgen_prototype_builder` | Build structures from AFLOW/ICSD prototype labels |
| `pymatgen_substitution_generator` | Generate structures by element substitution |
| `pymatgen_ion_exchange_generator` | Generate ion-exchanged variants of a structure |
| `pymatgen_perturbation_generator` | Randomly perturb atomic positions and lattice |
| `pymatgen_enumeration_generator` | Enumerate ordered supercell decorations of disordered structures (**requires enumlib**) |
| `predict_molecule_binding` | Predict molecule-target binding label with fixed fine-tuned LLM prompt (1 active / 0 inactive) |
| `predict_molecule_synthesizability` | Predict molecule synthesizability label with fixed fine-tuned LLM prompt (1 yes / 0 no / 2 unknown) |
