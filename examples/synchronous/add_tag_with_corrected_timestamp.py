import sys
import os

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.synchronous.sync_client import SyncClient
from ganzin.sol_sdk.requests import AddTagRequest, TagColor
from ganzin.sol_sdk.utils import get_timestamp_ms

def main():
    address, port = get_ip_and_port()
    sc = SyncClient(address, port)
    sc.begin_record()  # Tag can only be added during recording

    number_of_polls = 80
    print(f'Polls server {number_of_polls} times')
    result = sc.run_time_sync(number_of_polls)
    print(f'Time offset between client and server: {result.time_offset.mean} ms')
    print(f'Round trip: {result.round_trip.mean} ms')

    client_timestamp = get_timestamp_ms()
    projected_server_timestamp = client_timestamp - result.time_offset.mean
    print(f'client_timestamp={client_timestamp}; projected_server_timestamp={projected_server_timestamp}')
    color = TagColor.LightSeaGreen
    req = AddTagRequest('right moment', 'description', projected_server_timestamp, color)
    resp = sc.add_tag(req)
    print(f'Add tag result? {resp}')

    sc.end_record()

if __name__ == '__main__':
    main()
