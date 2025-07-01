from fastmcp.client import Client
import anyio

async def main():
    async with Client("http://localhost:9001/sse") as client:
        result = await client.call_tool("list_tables", {"database_name": ""}) # Adjust the database_name as needed
        print(result)

anyio.run(main)