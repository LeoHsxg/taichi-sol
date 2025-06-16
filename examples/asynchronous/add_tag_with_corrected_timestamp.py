import asyncio
import sys
import os

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.asynchronous.async_client import AsyncClient
from ganzin.sol_sdk.requests import AddTagRequest, TagColor
from ganzin.sol_sdk.utils import get_timestamp_ms

async def main():
    address, port = get_ip_and_port()
    async with AsyncClient(address, port) as ac:
        await ac.begin_record() # Tag can only be added during recording

        number_of_polls = 80
        print(f'Polls server {number_of_polls} times')
        result = await ac.run_time_sync(number_of_polls)
        print(f'Time offset between client and server: {result.time_offset.mean} ms')
        print(f'Round trip: {result.round_trip.mean} ms')

        client_timestamp = get_timestamp_ms()
        projected_server_timestamp = client_timestamp - result.time_offset.mean
        color = TagColor.LightSeaGreen
        req = AddTagRequest('right moment', 'describe it', projected_server_timestamp , color)
        resp = await ac.add_tag(req)
        print(f'Add tag result? {resp}')

        await ac.end_record()

if __name__ == "__main__":
    asyncio.run(main())
