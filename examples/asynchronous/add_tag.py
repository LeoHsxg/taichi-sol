import asyncio
import sys
import os

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.asynchronous.async_client import AsyncClient
from ganzin.sol_sdk.requests import AddTagRequest, TagColor

async def main():
    address, port = get_ip_and_port()
    async with AsyncClient(address, port) as ac:
        color = TagColor.LightSeaGreen
        req = AddTagRequest('right moment', 'description', 1719387152014, color)
        resp = await ac.add_tag(req)
        print(f'Add tag result? {resp}')

if __name__ == "__main__":
    asyncio.run(main())