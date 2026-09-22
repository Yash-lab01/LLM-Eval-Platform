"""FastMCP Server for LLM Evaluation & Benchmarking Platform.

Supports dual transport:
- stdio: for Cursor, Claude Desktop, and local IDE integration
- streamable-http: for network/dockerized services on port 8001
"""

import os

from fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("llm-eval-platform")


@mcp.tool()
async def health_check() -> dict:
    """Check MCP server health and connectivity status."""
    return {"status": "healthy", "service": "mcp-server"}


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if transport == "http":
        port = int(os.getenv("MCP_PORT", "8001"))
        host = os.getenv("MCP_HOST", "0.0.0.0")
        mcp.run(transport="sse", host=host, port=port)
    else:
        # stdio mode: all logs must go to stderr
        mcp.run(transport="stdio")
