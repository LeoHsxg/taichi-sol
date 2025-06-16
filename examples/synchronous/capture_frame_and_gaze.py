import sys
import os

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.synchronous.sync_client import SyncClient
from ganzin.sol_sdk.responses import CaptureResult

def main():
    address, port = get_ip_and_port()
    sc = SyncClient(address, port)
    resp = sc.capture()
    result = CaptureResult.from_raw(resp.result)
    print(f'timestamp = {result.timestamp}')
    print(f'gaze: x = {result.gaze_data.combined.gaze_2d.x}, y = {result.gaze_data.combined.gaze_2d.y}')
    with open("image_captured.jpg", "wb") as file:
        file.write(result.scene_image)
        print(f'Saved image to "{file.name}"') 

if __name__ == '__main__':
    main()