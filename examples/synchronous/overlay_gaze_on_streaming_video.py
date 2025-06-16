import sys
import os

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.streaming.gaze_stream import GazeData
from ganzin.sol_sdk.synchronous.models import StreamingMode
from ganzin.sol_sdk.synchronous.sync_client import SyncClient
from ganzin.sol_sdk.utils import find_nearest_timestamp_match
import cv2

def main():
    address, port = get_ip_and_port()
    sc = SyncClient(address, port)

    th = sc.create_streaming_thread(StreamingMode.GAZE_SCENE)
    th.start()

    try:
        while True:
            frame_data = sc.get_scene_frames_from_streaming(timeout=5.0)
            frame_datum = frame_data[-1] # get the last frame
            buffer = frame_datum.get_buffer()
            gazes = sc.get_gazes_from_streaming(timeout=5.0)
            gaze = find_nearest_timestamp_match(frame_datum.get_timestamp(), gazes)

            center = (int(gaze.combined.gaze_2d.x), int(gaze.combined.gaze_2d.y))
            radius = 30
            bgr_color = (255, 255, 0)
            thickness = 5
            cv2.circle(buffer, center, radius, bgr_color, thickness)

            cv2.imshow('Press "q" to exit', buffer)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except Exception as ex:
        print(ex)
    finally:
        th.cancel()
        th.join()
        print('Stopped')

if __name__ == '__main__':
    main()
