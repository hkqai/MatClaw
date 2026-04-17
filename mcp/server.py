"""
MatClaw MCP Server
"""

from dotenv import load_dotenv
import logging
from mcp.server.fastmcp import FastMCP
from tools.pubchem import (
    pubchem_search_compounds,
    pubchem_get_compound_properties,
    pubchem_search_compounds, 
    pubchem_get_compound_properties,
    pubchem_get_safety_data,
)
from tools.molport import (
    molport_search_molecules,
    molport_get_molecule_info,
)
from tools.materials_project import (
    mp_search_materials,
    mp_get_material_properties,
    mp_get_detailed_property_data,
    mp_search_recipe
)
from tools.ase import (
    ase_connect_or_create_db,
    ase_store_result,
    ase_query,
    ase_get_atoms,
    ase_list_databases
)
from tools.composition_generation import (
    composition_enumerator,
)
from tools.pymatgen import (
    pymatgen_prototype_builder,
    pymatgen_substitution_generator,
    pymatgen_substitution_predictor,
    pymatgen_ion_exchange_generator,
    pymatgen_perturbation_generator,
    pymatgen_enumeration_generator,
    pymatgen_defect_generator,
    pymatgen_sqs_generator,
    pymatgen_disorder_generator,
)
from tools.analysis import (
    structure_validator,
    composition_analyzer,
    structure_analyzer,
    stability_analyzer,
    structure_fingerprinter,
)
from tools.matgl import (
    matgl_relax_structure,
    matgl_predict_bandgap,
    matgl_predict_eform
)
from tools.chem_llm import (
    predict_molecule_binding,
    predict_molecule_synthesizability,
)
from tools.selection import (
    multi_objective_ranker,
)
from tools.synthesis_planning import (
    template_route_generator,
    synthesis_recipe_quantifier,
)
from tools.elemwise_retro import (
    er_predict_precursors,
    er_predict_temperature,
)
from tools.arrows import (
    arrows_initialize_campaign,
    arrows_suggest_experiment,
    arrows_record_result,
)
from tools.bayesian_optimization import (
    bo_initialize_campaign,
    bo_suggest_experiment,
    bo_record_result,
)
from tools.characterization import (
    xrd_analyze_pattern,
)
from tools.characterization import (
    xrd_analyze_pattern,
)
from tools.urdf import (
    urdf_validate,
    urdf_fix,
    urdf_inspect,
)
from tools.lula import (
    lula_generate_robot_description,
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp = FastMCP(name="matclaw-mcp-server")

# Add tools
# Pubchem tools
mcp.tool()(pubchem_search_compounds)
mcp.tool()(pubchem_get_compound_properties)
mcp.tool()(pubchem_get_safety_data)

# Materials Project tools
mcp.tool()(mp_search_materials)
mcp.tool()(mp_get_material_properties)
mcp.tool()(mp_get_detailed_property_data)
mcp.tool()(mp_search_recipe)

# Molport tools
mcp.tool()(molport_search_molecules)
mcp.tool()(molport_get_molecule_info)

# ASE database tools
mcp.tool()(ase_connect_or_create_db)
mcp.tool()(ase_store_result)
mcp.tool()(ase_query)
mcp.tool()(ase_get_atoms)
mcp.tool()(ase_list_databases)

# Composition generation tools
mcp.tool()(composition_enumerator)

# Pymatgen structure generation tools
mcp.tool()(pymatgen_prototype_builder)
mcp.tool()(pymatgen_substitution_generator)
mcp.tool()(pymatgen_substitution_predictor)
mcp.tool()(pymatgen_ion_exchange_generator)
mcp.tool()(pymatgen_perturbation_generator)
mcp.tool()(pymatgen_enumeration_generator)
mcp.tool()(pymatgen_defect_generator)
mcp.tool()(pymatgen_sqs_generator)
mcp.tool()(pymatgen_disorder_generator)

# Analysis tools for materials screening
mcp.tool()(structure_validator)
mcp.tool()(composition_analyzer)
mcp.tool()(structure_analyzer)
mcp.tool()(stability_analyzer)
mcp.tool()(structure_fingerprinter)

# Machine learning prediction tools
mcp.tool()(matgl_relax_structure)
mcp.tool()(matgl_predict_bandgap)
mcp.tool()(matgl_predict_eform)

# Fine-tuned LLM prediction tools
mcp.tool()(predict_molecule_binding)
mcp.tool()(predict_molecule_synthesizability)

# Selection and ranking tools
mcp.tool()(multi_objective_ranker)

# Synthesis planning tools
mcp.tool()(template_route_generator)
mcp.tool()(synthesis_recipe_quantifier)

# ElemwiseRetro tools
mcp.tool()(er_predict_precursors)
mcp.tool()(er_predict_temperature)

# ARROWS active learning tools
mcp.tool()(arrows_initialize_campaign)
mcp.tool()(arrows_suggest_experiment)
mcp.tool()(arrows_record_result)

# Bayesian optimization tools
mcp.tool()(bo_initialize_campaign)
mcp.tool()(bo_suggest_experiment)
mcp.tool()(bo_record_result)

# XRD analysis tools
mcp.tool()(xrd_analyze_pattern)

# URDF validation and fixing tools
mcp.tool()(urdf_validate)
mcp.tool()(urdf_fix)
mcp.tool()(urdf_inspect)

# Lula robot description generation
mcp.tool()(lula_generate_robot_description)



if __name__ == "__main__":
    logger.info("Starting MatClaw MCP Server")
    mcp.run()
