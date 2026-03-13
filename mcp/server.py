"""
MatClaw MCP Server
"""

import asyncio
import logging
from mcp.server.fastmcp import FastMCP
from mcp.types import Tool, TextContent
from tools.data_retrieval import pubchem_search_compounds

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP(name="matclaw-mcp-server")

mcp.tool()(pubchem_search_compounds)


if __name__ == "__main__":
    logger.info("Starting Materials Science MCP Server")
    mcp.run()