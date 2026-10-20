"""Local stdio client for the business MCP server."""

import asyncio
import os

from fastmcp import Client

MCP_URL = os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp")


async def main() -> None:
    # Connect to the HTTP MCP endpoint started by server.py.
    async with Client(MCP_URL) as client:
        tools = await client.list_tools()
        print("Available MCP tools:")
        for tool in tools:
            print(f"- {tool.name}: {tool.description}")

        # Example text search against product and part tables.
        # result = await client.call_tool(
        #     "search_products",
        #     {"query": "PCB-DEMO-001", "limit": 5},
        # )
        # print(result)


if __name__ == "__main__":
    asyncio.run(main())
