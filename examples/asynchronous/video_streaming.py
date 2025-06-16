import asyncio
import sys
import os

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.asynchronous.async_client import AsyncClient, recv_video
from ganzin.sol_sdk.common_models import Camera
import cv2


async def main():
    address, port = get_ip_and_port()
    async with AsyncClient(address, port) as ac:
        async for frame_data in recv_video(ac, Camera.SCENE):
            buffer = frame_data.get_buffer()
            cv2.imshow('Press "q" to exit', buffer)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                return


if __name__ == "__main__":
    asyncio.run(main())
