import cv2
import numpy

import sys
import os

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.common_models import Camera
from ganzin.sol_sdk.synchronous.models import StreamingMode
from ganzin.sol_sdk.synchronous.sync_client import SyncClient
from ganzin.sol_sdk.utils import find_nearest_timestamp_match


def main():
    address, port = get_ip_and_port()
    sc = SyncClient(address, port)
    if not sc.get_status().eye_image_encoding_enabled:
        print('Warning: Please enable eye image encoding and try again.')
        return

    th = sc.create_streaming_thread(StreamingMode.GAZE_SCENE_EYES)
    th.start()

    try:
        while True:
            frame_data = sc.get_scene_frames_from_streaming(timeout=5.0)
            frame_datum = frame_data[-1] # get the last frame
            buffer = frame_datum.get_buffer()
            gazes = sc.get_gazes_from_streaming(timeout=5.0)
            gaze = find_nearest_timestamp_match(frame_datum.get_timestamp(), gazes)
            left_eye_data = sc.get_left_eye_frames_from_streaming(timeout=5.0)
            left_eye_datum = find_nearest_timestamp_match(frame_datum.get_timestamp(), left_eye_data)
            right_eye_data = sc.get_right_eye_frames_from_streaming(timeout=5.0)
            right_eye_datum = find_nearest_timestamp_match(frame_datum.get_timestamp(), right_eye_data)

            # Overlay gaze on scene camera frame
            center = (int(gaze.combined.gaze_2d.x), int(gaze.combined.gaze_2d.y))
            radius = 30
            bgr_color = (255, 255, 0)
            thickness = 5
            cv2.circle(buffer, center, radius, bgr_color, thickness)

            resize_ratio = 0.5
            # Overlay left eye on scene camera frame
            left_eye_frame = left_eye_datum.get_buffer()
            draw_to_center_top(buffer, left_eye_frame, Camera.LEFT_EYE, resize_ratio)

            # Overlay right eye on scene camera frame
            right_eye_frame = right_eye_datum.get_buffer()
            draw_to_center_top(buffer, right_eye_frame, Camera.RIGHT_EYE, resize_ratio)

            cv2.imshow('Press "q" to exit', buffer)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except Exception as ex:
        print(ex)
    finally:
        th.cancel()
        th.join()
        print('Stopped')

def draw_to_center_top(scene_cam_frame: numpy.ndarray, \
                       eye_frame: numpy.ndarray, camera: Camera, \
                       ratio: float = 1.0, center_margin = 5) \
      -> tuple[int, int]:
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
    main()
