import sys
import os
import asyncio

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.server_info import get_ip_and_port
from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.asynchronous.async_client import AsyncClient, recv_audio
from ganzin.sol_sdk.common_models import Camera
from ganzin.sol_sdk.streaming.audio_config import AudioConfig

import pyaudio


def initialize_audio_stream(config: AudioConfig):
    audio = pyaudio.PyAudio()
    # Use paFloat32 to match the decoder's "fltp" (floating-point planar) output format.
    stream = audio.open(
        format=pyaudio.paFloat32,
        channels=config.num_channels,
        rate=config.sample_rate,
        output=True,
    )
    return stream


def create_stream_updater(ref_list):
    return (
        lambda config: ref_list.__setitem__(0, initialize_audio_stream(config))
        or ref_list[0]
    )


async def main():
    address, port = get_ip_and_port()
    streams = [None]

    # Create a callback function that initializes the audio stream when
    # new audio configuration is received. This function updates the stream
    # reference in the streams list.
    update_audio_stream = create_stream_updater(streams)

    try:
        async with AsyncClient(address, port) as ac:
            if not (await ac.get_status()).audio_enabled:
                print("Warning: Please enable 'Microphone' in the server settings.")
                return

            print("Audio playback started. Press Ctrl+C to stop.")
            async for frame in recv_audio(ac, Camera.SCENE, update_audio_stream):
                streams[0].write(frame.get_pcm())
    finally:
        # Clean up audio resources
        if streams[0] is not None:
            print("\nCleaning up audio resources...")
            streams[0].stop_stream()
            streams[0].close()

            # Get parent PyAudio instance and terminate it
            pa = streams[0]._parent
            pa.terminate()

            streams[0] = None

            print("Audio playback stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
