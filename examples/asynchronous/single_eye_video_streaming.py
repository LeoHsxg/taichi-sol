import asyncio
import cv2
import time

import sys
import os

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.asynchronous.async_client import AsyncClient, recv_video
from ganzin.sol_sdk.common_models import Camera

async def main():
    address, port = get_ip_and_port()

    target_fps = 60
    frame_interval = 1 / target_fps
    
    async with AsyncClient(address, port) as ac:
        if not (await ac.get_status()).eye_image_encoding_enabled:
            print('Warning: Please enable eye image encoding and try again.')
            return

        last_frame_time = time.perf_counter()

        async for frame_data in recv_video(ac, Camera.LEFT_EYE): # Camera.RIGHT_EYE works too.
            buffer = frame_data.get_buffer()
            cv2.imshow('Press "q" to exit', buffer)

            elapsed_time_since_last_frame = time.perf_counter() - last_frame_time
            if elapsed_time_since_last_frame > frame_interval:
               if cv2.waitKey(1) & 0xFF == ord('q'):
                   return
               last_frame_time = time.perf_counter()

if __name__ == "__main__":
    asyncio.run(main())
