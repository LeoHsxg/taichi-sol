import sys
import os

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.synchronous.sync_client import SyncClient

def main():
    address, port = get_ip_and_port()
    sc = SyncClient(address, port)
    resp = sc.get_status()
    print(resp)

if __name__ == '__main__':
    main()