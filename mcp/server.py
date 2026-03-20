"""
MatClaw MCP Server
"""

from dotenv import load_dotenv
import logging
from mcp.server.fastmcp import FastMCP
from tools.pubchem import (
    pubchem_search_compounds, 
    pubchem_get_compound_properties, 
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
from tools.pymatgen import (
    pymatgen_prototype_builder,
    pymatgen_substitution_generator,
    pymatgen_ion_exchange_generator,
    pymatgen_perturbation_generator,
    pymatgen_enumeration_generator,
    pymatgen_defect_generator,
    pymatgen_sqs_generator,
)
from tools.urdf import (
    urdf_validate,
    urdf_fix,
    urdf_inspect,
)
from tools.analysis import (
    structure_validator,
    composition_analyzer,
    structure_analyzer,
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp = FastMCP(name="matclaw-mcp-server")

# Add tools
# Data retrieval tools
mcp.tool()(pubchem_search_compounds)
mcp.tool()(pubchem_get_compound_properties)
mcp.tool()(mp_search_materials)
mcp.tool()(mp_get_material_properties)
mcp.tool()(mp_get_detailed_property_data)
mcp.tool()(mp_search_recipe)

# ASE database tools
mcp.tool()(ase_connect_or_create_db)
mcp.tool()(ase_store_result)
mcp.tool()(ase_query)
mcp.tool()(ase_get_atoms)
mcp.tool()(ase_list_databases)

# Pymatgen structure generation tools
mcp.tool()(pymatgen_prototype_builder)
mcp.tool()(pymatgen_substitution_generator)
mcp.tool()(pymatgen_ion_exchange_generator)
mcp.tool()(pymatgen_perturbation_generator)
mcp.tool()(pymatgen_enumeration_generator)
mcp.tool()(pymatgen_defect_generator)
mcp.tool()(pymatgen_sqs_generator)

# URDF validation and fixing tools
mcp.tool()(urdf_validate)
mcp.tool()(urdf_fix)
mcp.tool()(urdf_inspect)

# Analysis tools for materials screening
mcp.tool()(structure_validator)
mcp.tool()(composition_analyzer)
mcp.tool()(structure_analyzer)


if __name__ == "__main__":
    logger.info("Starting MatClaw MCP Server")
    mcp.run()
