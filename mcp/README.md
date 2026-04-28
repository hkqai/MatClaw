# MatClaw MCP Server

MCP (Model Context Protocol) server exposing tools for inorganic materials discovery.

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

## Installation

### Linux / macOS (recommended)

```bash
cd mcp/

# Full setup — creates venv, installs pip packages
bash setup.sh

# Activate the venv
source venv/bin/activate
```

### Windows (native)

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

Run tests for a particular module:
```bash
python -m pytest tests/pymatgen/test_enumeration_generator.py -v
```

---

## Tools

### URDF (Robotics)

| Tool | Description |
|---|---|
| `urdf_validate` | Validate URDF robot models for Isaac Sim / USD compatibility |
| `urdf_fix` | Automatically fix common URDF errors for Isaac Sim / USD compatibility |
| `urdf_inspect` | Inspect and analyze URDF structure: kinematic tree, mass distribution, mesh files, materials, joint breakdown |

### Lula (Robotics)

| Tool | Description |
|---|---|
| `lula_generate_robot_description` | Generate Lula robot description with automatic collision-sphere placement for NVIDIA Isaac Sim |

### Pubchem Data Retrieval

| Tool | Description |
|---|---|
| `pubchem_search_compounds` | Search PubChem by name, SMILES, formula, InChIKey |
| `pubchem_get_compound_properties` | Get detailed properties for PubChem CIDs |
| `pubchem_get_safety_data` | Get safety data (GHS classification, hazards, precautions) for compounds |

### Materials Project Data Retrieval

| Tool | Description |
|---|---|
| `mp_search_materials` | Search Materials Project for inorganic crystals |
| `mp_get_material_properties` | Get detailed properties for MP material IDs |
| `mp_get_detailed_property_data` | Get band structure, DOS, elastic tensor, etc. |
| `mp_search_recipe` | Search Synthesis Explorer for experimental recipes |

### ASE Database

| Tool | Description |
|---|---|
| `ase_connect_or_create_db` | Connect to or create an ASE SQLite database |
| `ase_store_result` | Store an Atoms object and results to the database |
| `ase_query` | Query the ASE database by formula, property, tag |
| `ase_get_atoms` | Retrieve full Atoms objects from the database |
| `ase_list_databases` | List and summarize ASE .db files in a directory |

### Composition Generation

| Tool | Description |
|---|---|
| `composition_enumerator` | Enumerate charge-balanced compositions from element lists for composition-space exploration |

### Pymatgen Candidate Generation

| Tool | Description |
|---|---|
| `pymatgen_prototype_builder` | Build structures from spacegroup, species, and lattice parameters |
| `pymatgen_substitution_predictor` | Predict likely element substitutions using ICSD data mining (composition → composition) |
| `pymatgen_substitution_generator` | Generate structures by element substitution |
| `pymatgen_ion_exchange_generator` | Generate ion-exchanged variants with charge balancing |
| `pymatgen_perturbation_generator` | Randomly perturb atomic positions and lattice |
| `pymatgen_enumeration_generator` | Enumerate ordered supercell decorations of disordered structures |
| `pymatgen_defect_generator` | Generate point defect supercells (vacancies, substitutions, interstitials) |
| `pymatgen_sqs_generator` | Generate special quasirandom structures (SQS) for alloy modeling |

### Analysis

| Tool | Description |
|---|---|
| `structure_validator` | Validate crystal structures (distances, symmetry, charge, stability) |
| `composition_analyzer` | Extract composition-based ML features (elemental properties, statistics) |
| `structure_analyzer` | Extract structure-based ML features (coordination, packing, RDF) |
| `stability_analyzer` | Analyze thermodynamic stability (formation energy, hull distance) |
| `structure_fingerprinter` | Generate structural fingerprints (SOAP, MBTR, Sine/Coulomb matrices) |

### ML Prediction

| Tool | Description |
|---|---|
| `matgl_relax_structure` | Relax crystal structures using M3GNet universal ML potential |
| `matgl_predict_bandgap` | Predict band gap using pre-trained MEGNet model |
| `matgl_predict_eform` | Predict formation energy using pre-trained MEGNet model |

### ChemLLM

| Tool | Description |
|---|---|
| `predict_molecule_binding` | Predict molecule-target binding label with fine-tuned LLM |
| `predict_molecule_synthesizability` | Predict molecule synthesizability with fine-tuned LLM |

### Selection & Ranking

| Tool | Description |
|---|---|
| `multi_objective_ranker` | Multi-objective optimization (Pareto, weighted sum, constraint-based) |

### ORCA (Quantum Chemistry)

| Tool | Description |
|---|---|
| `orca_analysis_tools` | Parse and summarize ORCA output files (energies, HOMO/LUMO, frequencies) |
| `orca_cube_tools` | Generate molecular orbital, electron density, and ESP cube files from ORCA calculations |

### Synthesis Planning

| Tool | Description |
|---|---|
| `synthesis_recipe_quantifier` | Extract and quantify synthesis parameters from text recipes |

### ElemwiseRetro

| Tool | Description |
|---|---|
| `er_predict_precursors` | Predict optimal synthesis precursors for inorganic materials |
| `er_predict_temperature` | Predict synthesis temperature given target and precursor set |

### ARROWS

| Tool | Description |
|---|---|
| `arrows_initialize_campaign` | Initialize ARROWS active learning campaign with thermodynamic precursor ranking |
| `arrows_suggest_experiment` | Suggest next experiment using acquisition function (uncertainty, diversity, random) |
| `arrows_record_result` | Record experimental result and update ARROWS reaction knowledge |

### Bayesian Optimization

| Tool | Description |
|---|---|
| `bo_initialize_campaign` | Initialize generic BO campaign with customizable parameter space (continuous, discrete, categorical) and objectives |
| `bo_record_result` | Record experimental observations (any measurement types: XRD, SEM, electrochemical, etc.) |
| `bo_suggest_experiment` | Suggest next experiments using GP model and acquisition functions (EI, UCB, PI) |

### Characterization

| Tool | Description |
|---|---|
| `xrd_analyze_pattern` | Automated XRD phase identification using autoXRD deep learning model |

### Image Retrieval

| Tool | Description |
|---|---|
| `paper_image_extract` | Extract figures and images from scientific papers (PDF) |
| `image_segmentation` | Segment images into regions using ML models |
| `sem_image_classification` | Classify SEM images by morphology or composition |
