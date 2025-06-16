import sys
import os

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.synchronous.models import StreamingMode
from ganzin.sol_sdk.synchronous.sync_client import SyncClient
import cv2

def main():
    address, port = get_ip_and_port()
    sc = SyncClient(address, port)

    th = sc.create_streaming_thread(StreamingMode.SCENE)
    th.start()

    try:
        while True:
            frame_data = sc.get_scene_frames_from_streaming(timeout=5.0)
            frame_datum = frame_data[-1] # get the last frame
            cv2.imshow('Press "q" to quit', frame_datum.get_buffer())
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except Exception as ex:
        print(ex)
    finally:
        print('Stopped')

    th.cancel()
    th.join()

if __name__ == '__main__':
    main()
