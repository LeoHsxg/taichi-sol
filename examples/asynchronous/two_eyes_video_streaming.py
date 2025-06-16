import asyncio
import cv2
import numpy as np

import sys
import os

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.asynchronous.async_client import AsyncClient, recv_video
from ganzin.sol_sdk.common_models import Camera

async def main():
    address, port = get_ip_and_port()
    
    async with AsyncClient(address, port) as ac:
        if not (await ac.get_status()).eye_image_encoding_enabled:
            print('Warning: Please enable eye image encoding and try again.')
            return

        left_eye_queue = asyncio.Queue(maxsize=1)
        right_eye_queue = asyncio.Queue()

        collect_left_eye_task = asyncio.create_task(keep_last_video_frame(ac, left_eye_queue))
        collect_right_eye_task = asyncio.create_task(collect_video_frame(ac, right_eye_queue))

        try:
            await draw_eyes(left_eye_queue, right_eye_queue)
        except Exception as e:
            print(f'Error: {e}')
        finally:
            collect_left_eye_task.cancel()
            collect_right_eye_task.cancel()

async def keep_last_video_frame(ac: AsyncClient, queue: asyncio.Queue):
    async for frame in recv_video(ac, Camera.LEFT_EYE):
        if queue.full():
            queue.get_nowait()
        queue.put_nowait(frame)

async def collect_video_frame(ac: AsyncClient, queue: asyncio.Queue):
    async for gaze in recv_video(ac, Camera.RIGHT_EYE):
        await queue.put(gaze)

async def draw_eyes(queue_left, queue_right):
    while True:
        left_data = await queue_left.get()
        right_data = await find_nearest_frame(queue_right, left_data.get_timestamp())

        combined_img = np.hstack((left_data.get_buffer(), right_data.get_buffer()))
        cv2.imshow('Press "q" to exit', combined_img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

async def find_nearest_frame(queue, timestamp):
    item = await queue.get()
    if item.get_timestamp() > timestamp:
        return item

    while True:
        if queue.empty():
            return item
        else:
            next_item = queue.get_nowait()
            if next_item.get_timestamp() > timestamp:
                return next_item
            item = next_item

if __name__ == "__main__":
    asyncio.run(main())
