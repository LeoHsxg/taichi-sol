"""
This Python file demonstrates how to play streaming audio and video in
sync using timestamps.

It serves as an example for synchronizing playback of audio and video
streams, ensuring both media types are played together in real time
according to their respective timestamps.
"""

import asyncio
import queue
import signal
import threading
import time

import cv2
import pyaudio

import sys
import os

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.asynchronous.async_client import AsyncClient, recv_av
from ganzin.sol_sdk.common_models import Camera
from ganzin.sol_sdk.streaming.audio_config import AudioConfig
from ganzin.sol_sdk.streaming.audio_frame import AudioFrame
from ganzin.sol_sdk.streaming.video_frame import VideoFrame

# Constants
MILLISECONDS_PER_SECOND = 1000
BUFFER_DURATION_MS = 800


class PeekableQueue(queue.Queue):
    def peek(self):
        with self.mutex:  # Thread-safe access to the internal deque
            if not self._qsize():
                raise queue.Empty
            return self.queue[0]


class PlaybackState:
    def __init__(self):
        self.first_media_ts = None
        self.playback_ready_time_ms = None
        self.audio_output_latency_ms = None
        self.lock = threading.Lock()

    def set_first_media_ts(self, media_ts):
        with self.lock:
            self.first_media_ts = media_ts

    def set_playback_ready_time_ms(self, elapsed):
        with self.lock:
            self.playback_ready_time_ms = elapsed

    def get_states(self):
        with self.lock:
            return (
                self.first_media_ts,
                self.playback_ready_time_ms,
                self.audio_output_latency_ms,
            )

    def set_output_delay_ms(self, value):
        with self.lock:
            self.audio_output_latency_ms = value


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


def play_audio(audio_queue, state: PlaybackState, stop_event, audio_output):
    """Thread function to play audio frames."""
    while not stop_event.is_set():
        try:
            first_media_ts, playback_ready_time_ms, _ = state.get_states()
            if first_media_ts and playback_ready_time_ms:
                audio_frame = audio_queue.peek()
                elapsed_ms = audio_frame.get_timestamp() - first_media_ts
                if elapsed_ms <= playback_ready_time_ms:
                    audio_queue.get(timeout=0.1)  # really take the element out
                    audio_output[0].write(audio_frame.get_pcm())
        except queue.Empty:
            continue


def play_video(video_queue, state: PlaybackState, stop_event):
    """Thread function to display video frames."""
    while not stop_event.is_set():
        try:
            first_media_ts, playback_ready_time_ms, audio_output_latency_ms = (
                state.get_states()
            )
            if first_media_ts and playback_ready_time_ms:
                video_frame = video_queue.peek()
                elapsed_ms = video_frame.get_timestamp() - first_media_ts

                if elapsed_ms < 0:
                    # Skip video frame that appears earlier than audio.
                    video_queue.get(timeout=0.1)
                elif elapsed_ms + audio_output_latency_ms <= playback_ready_time_ms:
                    video_queue.get(timeout=0.1)  # really take the frame out
                    buffer = video_frame.get_buffer()
                    buffer = cv2.resize(
                        buffer, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA
                    )
                    cv2.imshow('Press "q" to exit', buffer)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                stop_event.set()  # Signal all threads to stop
                break
        except queue.Empty:
            continue


async def main(stop_event):
    address, port = get_ip_and_port()
    audio_streams = [None]

    # Create a callback function that initializes the audio stream when
    # new audio configuration is received. This function updates the stream
    # reference in the audio_streams list.
    update_audio_stream = create_stream_updater(audio_streams)

    audio_queue = PeekableQueue()
    video_queue = PeekableQueue()
    state = PlaybackState()
    audio_thread = threading.Thread(
        target=play_audio, args=(audio_queue, state, stop_event, audio_streams)
    )
    video_thread = threading.Thread(
        target=play_video, args=(video_queue, state, stop_event)
    )

    is_thread_started = False
    start_time = None

    try:
        async with AsyncClient(address, port) as ac:
            if not (await ac.get_status()).audio_enabled:
                print("Warning: Please enable 'Microphone' in the server settings.")
                return

            print("Audio-Video playback started. Press Ctrl+C to stop.")
            async for frame_data in recv_av(ac, Camera.SCENE, update_audio_stream):
                if isinstance(frame_data, AudioFrame):
                    audio_queue.put(frame_data)

                    curr_ts = frame_data.get_timestamp()
                    first_audio_ts, _, _ = state.get_states()
                    if first_audio_ts == None:
                        first_audio_ts = curr_ts
                        state.set_first_media_ts(curr_ts)
                        state.set_output_delay_ms(
                            audio_streams[0].get_output_latency()
                            * MILLISECONDS_PER_SECOND
                        )
                        print("first audio ts is set")

                    # Once enough buffered data has accumulated
                    # (determined by BUFFER_DURATION_MS),
                    # start both audio and video playback threads.
                    if (
                        not is_thread_started
                        and first_audio_ts
                        and curr_ts - first_audio_ts > BUFFER_DURATION_MS
                    ):
                        is_thread_started = True
                        audio_thread.start()
                        video_thread.start()
                        start_time = time.perf_counter()
                        print("Start audio thread")

                    # Update playback ready time
                    if start_time:
                        state.set_playback_ready_time_ms(
                            (time.perf_counter() - start_time) * MILLISECONDS_PER_SECOND
                        )
                elif isinstance(frame_data, VideoFrame):
                    video_queue.put(frame_data)

                if stop_event.is_set():
                    break
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        if is_thread_started:
            print("Stopping playback...")
            stop_event.set()
            audio_thread.join()
            video_thread.join()

        # Clean up audio resources
        if audio_streams[0] is not None:
            print("\nCleaning up audio resources...")
            audio_streams[0].stop_stream()
            audio_streams[0].close()

            # Get parent PyAudio instance and terminate it
            pa = audio_streams[0]._parent
            pa.terminate()

            audio_streams[0] = None
            print("Playback stopped.")


def custom_signal_handler(signum, frame, stop_event):
    """Custom signal handler to set the stop_event when Ctrl-C is pressed."""
    stop_event.set()  # Signal the event to stop


if __name__ == "__main__":
    stop_event = threading.Event()  # Create a threading event to signal stopping

    # Set the custom signal handler for Ctrl-C (SIGINT)
    signal.signal(signal.SIGINT, lambda s, f: custom_signal_handler(s, f, stop_event))

    asyncio.run(main(stop_event))
