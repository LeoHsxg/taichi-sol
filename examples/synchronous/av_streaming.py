"""
This Python file demonstrates how to play streaming audio and video in
sync using timestamps.

It serves as an example for synchronizing playback of audio and video
streams, ensuring both media types are played together in real time
according to their respective timestamps.
"""

import cv2
import pyaudio
import queue
import threading
import time

import sys
import os

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.streaming.audio_config import AudioConfig
from ganzin.sol_sdk.streaming.audio_frame import AudioFrame
from ganzin.sol_sdk.streaming.video_frame import VideoFrame
from ganzin.sol_sdk.synchronous.models import StreamingMode
from ganzin.sol_sdk.synchronous.sync_client import SyncClient

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


def play_audio(audio_output, audio_queue, state: PlaybackState, stop_event):
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
            first_media_ts, playback_ready_time_ms, output_output_latency_ms = (
                state.get_states()
            )
            if first_media_ts and playback_ready_time_ms:
                video_frame = video_queue.peek()
                elapsed_ms = video_frame.get_timestamp() - first_media_ts

                if elapsed_ms < 0:
                    # Skip video frame that appears earlier than audio.
                    video_queue.get(timeout=0.1)
                elif elapsed_ms + output_output_latency_ms <= playback_ready_time_ms:
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


def main():
    address, port = get_ip_and_port()
    sc = SyncClient(address, port)
    if not sc.get_status().audio_enabled:
        print("Warning: Please enable 'Microphone' in the server settings.")
        return

    audio_streams = [None]

    # Create a callback function that initializes the audio stream when
    # new audio configuration is received. This function updates the stream
    # reference in the streams list.
    update_audio_stream = create_stream_updater(audio_streams)

    print("Audio-Video playback started. Press Ctrl+C to stop.")

    th = sc.create_streaming_thread(StreamingMode.AUDIO_VIDEO, update_audio_stream)
    th.start()

    audio_queue = PeekableQueue()
    video_queue = PeekableQueue()
    stop_event = threading.Event()  # Create stop event

    state = PlaybackState()

    # Create and start threads for audio and video playback
    audio_thread = threading.Thread(
        target=play_audio, args=(audio_streams, audio_queue, state, stop_event)
    )
    video_thread = threading.Thread(
        target=play_video, args=(video_queue, state, stop_event)
    )

    are_threads_started = False
    start_time = None

    try:
        while not stop_event.is_set():
            frames = sc.get_av_frames_from_streaming(timeout=0.5)
            if frames:
                for frame_datum in frames:
                    if isinstance(frame_datum, AudioFrame):
                        audio_queue.put(frame_datum)

                        curr_ts = frame_datum.get_timestamp()
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
                            not are_threads_started
                            and first_audio_ts
                            and curr_ts - first_audio_ts > BUFFER_DURATION_MS
                        ):
                            are_threads_started = True
                            audio_thread.start()
                            video_thread.start()
                            start_time = time.perf_counter()
                            print("Start audio thread")

                        # Update playback ready time
                        if start_time:
                            state.set_playback_ready_time_ms(
                                (time.perf_counter() - start_time)
                                * MILLISECONDS_PER_SECOND
                            )

                    elif isinstance(frame_datum, VideoFrame):
                        video_queue.put(frame_datum)
            else:
                # Yield execution to allow the data collection thread to process incoming data
                time.sleep(0.01)
    except KeyboardInterrupt:  # Press Ctrl-C to stop
        stop_event.set()
    except Exception as ex:
        print(ex)
    finally:
        # Wait for threads to finish
        audio_thread.join()
        video_thread.join()

        th.cancel()
        th.join()

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


if __name__ == "__main__":
    main()
