import asyncio
import cv2
import numpy

import sys
import os

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.asynchronous.async_client import AsyncClient, recv_gaze, recv_video
from ganzin.sol_sdk.common_models import Camera
from ganzin.sol_sdk.utils import find_nearest_timestamp_match


async def main():
    address, port = get_ip_and_port()
    timeout_seconds = 5.0

    async with AsyncClient(address, port) as ac:
        if not (await ac.get_status()).eye_image_encoding_enabled:
            print('Warning: Please enable eye image encoding and try again.')
            return

        error_event = asyncio.Event()

        frames = asyncio.Queue(1)
        collect_video_task = asyncio.create_task(keep_last_video_frame(ac, frames, error_event))

        gazes = asyncio.Queue()       
        collect_gaze_task = asyncio.create_task(collect_gaze(ac, gazes, error_event, timeout_seconds))

        left_eye_data = asyncio.Queue()
        collect_left_eye_task = asyncio.create_task(
            collect_eye(ac, left_eye_data, Camera.LEFT_EYE, error_event, timeout_seconds))
        
        right_eye_data = asyncio.Queue()
        collect_right_eye_task = asyncio.create_task(
            collect_eye(ac, right_eye_data, Camera.RIGHT_EYE, error_event, timeout_seconds))

        try:
            await present(frames, gazes, left_eye_data, right_eye_data, \
                          error_event, timeout_seconds)
        except Exception as e:
            error_message = str(e)
            print("An error occurred: ", error_message if error_message else type(e))
        finally:
            collect_video_task.cancel()
            collect_gaze_task.cancel()
            collect_left_eye_task.cancel()
            collect_right_eye_task.cancel()

async def keep_last_video_frame(ac: AsyncClient, queue: asyncio.Queue, error_event: asyncio.Event) -> None:
    async for frame in recv_video(ac, Camera.SCENE):
        if error_event.is_set():
            break

        if queue.full():
            queue.get_nowait()
        queue.put_nowait(frame)

async def collect_gaze(ac: AsyncClient, queue: asyncio.Queue, error_event: asyncio.Event, timeout) -> None:
    try:
        async for gaze in recv_gaze(ac):
            if error_event.is_set():
                break

            await asyncio.wait_for(queue.put(gaze), timeout=timeout)
    except Exception as e:
        error_event.set()

async def collect_eye(ac: AsyncClient, queue: asyncio.Queue, camera: Camera, error_event: asyncio.Event, timeout) -> None:
    try:
        async for eye in recv_video(ac, camera):
            if error_event.is_set():
                break

            await asyncio.wait_for(queue.put(eye), timeout=timeout)
    except Exception as e:
        error_event.set()

async def present(frames, gaze_queue, left_eye_queue, right_eye_queue, error_event: asyncio.Event, timeout):
    while not error_event.is_set():
        scene_camera_datum = await get_video_frame(frames, timeout)
        timestamp = scene_camera_datum.get_timestamp()

        gazes = await get_all_queue_items(gaze_queue, timeout)
        gaze = find_nearest_timestamp_match(timestamp, gazes)

        left_eye_data = await get_all_queue_items(left_eye_queue, timeout)
        left_eye = find_nearest_timestamp_match(timestamp, left_eye_data)

        right_eye_data = await get_all_queue_items(right_eye_queue, timeout)
        right_eye = find_nearest_timestamp_match(timestamp, right_eye_data)

        buffer = scene_camera_datum.get_buffer()
        draw_gaze(gaze, buffer)
        draw_to_center_top(buffer, left_eye.get_buffer(), Camera.LEFT_EYE, 0.5)
        draw_to_center_top(buffer, right_eye.get_buffer(), Camera.RIGHT_EYE, 0.5)

        cv2.imshow('Press "q" to exit', buffer)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            return

async def get_video_frame(queue, timeout):
    return await asyncio.wait_for(queue.get(), timeout=timeout)

async def get_all_queue_items(queue, timeout):
    items = []
   
    # Wait for the first item with timeout
    item = await asyncio.wait_for(queue.get(), timeout=timeout)
    items.append(item)
    
    # Continue retrieving items until the queue is empty
    while True:
        try:
            item = queue.get_nowait()
            items.append(item)
        except asyncio.QueueEmpty:
            break
    return items

def draw_gaze(gaze, frame):
    center = (int(gaze.combined.gaze_2d.x), int(gaze.combined.gaze_2d.y))
    radius = 30
    bgr_color = (255, 255, 0)
    thickness = 5
    cv2.circle(frame, center, radius, bgr_color, thickness)
    return frame

def draw_to_center_top(
        scene_cam_frame: numpy.ndarray,
        eye_frame: numpy.ndarray, camera: Camera,
        ratio: float = 1.0,
        center_margin = 5
) -> tuple[int, int]:
    half_frame_width = scene_cam_frame.shape[1] // 2
    pos_x = half_frame_width
    pos_y = 0
    resized_eye_width = int(eye_frame.shape[1] * ratio)
    resized_eye_height = int(eye_frame.shape[0] * ratio)
    resized_eye = cv2.resize(eye_frame, (resized_eye_width, resized_eye_height))

    match camera:
        case Camera.LEFT_EYE:
            pos_x -= (resized_eye_width + center_margin)

        case Camera.RIGHT_EYE:
            pos_x += center_margin
            pass
        case _:
            raise ValueError(f"Invalid camera type: {camera}")

    scene_cam_frame[pos_y:pos_y + resized_eye_height, \
                    pos_x:pos_x + resized_eye_width] = resized_eye

if __name__ == '__main__':
    asyncio.run(main())
