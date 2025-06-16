import asyncio
import sys
import os

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.asynchronous.async_client import AsyncClient, recv_gaze

async def main():
    address, port = get_ip_and_port()
    async with AsyncClient(address, port) as ac:
        async for data in recv_gaze(ac):
            print(f'gaze: x = {data.combined.gaze_2d.x}, y = {data.combined.gaze_2d.y}')

if __name__ == "__main__":
    asyncio.run(main())
