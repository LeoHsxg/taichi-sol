import cv2
import numpy

import sys
import os

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.synchronous.models import StreamingMode
from ganzin.sol_sdk.synchronous.sync_client import SyncClient
from ganzin.sol_sdk.utils import find_nearest_timestamp_match

def main():
    address, port = get_ip_and_port()
    sc = SyncClient(address, port)
    if not sc.get_status().eye_image_encoding_enabled:
        print('Warning: Please enable eye image encoding and try again.')
        return

    th = sc.create_streaming_thread(StreamingMode.EYES)
    th.start()

    try:
        while True:
            left_eye_data = sc.get_left_eye_frames_from_streaming(timeout=5.0)
            right_eye_data = sc.get_right_eye_frames_from_streaming()
            left_eye_datum = left_eye_data[0]
            right_eye_datum = find_nearest_timestamp_match(left_eye_datum.get_timestamp(), right_eye_data)
            combined_img = numpy.hstack((left_eye_datum.get_buffer(), right_eye_datum.get_buffer()))
            
            cv2.imshow('Press "q" to quit', combined_img)
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
