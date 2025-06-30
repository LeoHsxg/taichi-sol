import pyaudio
import sys
import os

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.streaming.audio_config import AudioConfig
from ganzin.sol_sdk.synchronous.models import StreamingMode
from ganzin.sol_sdk.synchronous.sync_client import SyncClient


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


def main():
    address, port = get_ip_and_port()
    sc = SyncClient(address, port)
    if not sc.get_status().audio_enabled:
        print("Warning: Please enable 'Microphone' in the server settings.")
        return

    streams = [None]

    # Create a callback function that initializes the audio stream when
    # new audio configuration is received. This function updates the stream
    # reference in the streams list.
    update_audio_stream = create_stream_updater(streams)

    print("Audio playback started. Press Ctrl+C to stop.")

    th = sc.create_streaming_thread(StreamingMode.AUDIO, update_audio_stream)
    th.start()

    try:
        while True:
            frame_data = sc.get_audio_frames_from_streaming(timeout=5.0)
            if not frame_data:
                continue
            for sample in frame_data:
                streams[0].write(sample.get_pcm())

    except KeyboardInterrupt:  # Press Ctrl-C to stop
        pass
    except Exception as ex:
        print(ex)
    finally:
        print("Stopped")

    th.cancel()
    th.join()


if __name__ == "__main__":
    main()
