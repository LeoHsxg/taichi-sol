"""
This Python file demonstrates how to play streaming audio, video, and gaze
in sync using timestamps.

It serves as an example for synchronizing playback of audio, video, and gaze
streams, ensuring all media types are played together in real time according
to their respective timestamps.
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


class PlaybackTimingTracker:
    def __init__(self, start_event: threading.Event, audio_streams):
        self.start_event = start_event
        self.audio_streams = audio_streams
        self.first_media_ts = None
        self.is_playback_started = False
        self.start_time = None
        self.playback_ready_time_ms = None
        self.audio_output_latency_ms = None

    def update_on_data(self, frame):
        curr_ts = frame.get_timestamp()
        if self.first_media_ts == None:
            self.first_media_ts = curr_ts
            print("First audio ts is set.")

        if (
            not self.is_playback_started
            and self.first_media_ts
            and curr_ts - self.first_media_ts > BUFFER_DURATION_MS
        ):
            self.is_playback_started = True
            self.start_time = time.perf_counter()
            latency = self.audio_streams[0].get_output_latency()
            self.audio_output_latency_ms = latency * MILLISECONDS_PER_SECOND
            self.start_event.set()
            print("Start playback.")

        if self.start_time:
            elapsed = time.perf_counter() - self.start_time
            self.playback_ready_time_ms = elapsed * MILLISECONDS_PER_SECOND


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


def play_audio(
    audio_output, audio_queue, start_event, tracker: PlaybackTimingTracker, stop_event
):
    while not stop_event.is_set():
        if start_event.wait(timeout=0.01):
            break
    if stop_event.is_set():
        return

    print("play_audio starts.")
    while not stop_event.is_set():
        try:
            if tracker.first_media_ts and tracker.playback_ready_time_ms:
                audio_frame = audio_queue.peek()
                elapsed_ms = audio_frame.get_timestamp() - tracker.first_media_ts
                if elapsed_ms <= tracker.playback_ready_time_ms:
                    audio_queue.get(timeout=0.1)  # Really take the element out
                    audio_output[0].write(audio_frame.get_pcm())
        except queue.Empty:
            continue


def display_video_and_gaze(
    video_queue, gaze_queue, start_event, tracker: PlaybackTimingTracker, stop_event
):
    while not stop_event.is_set():
        if start_event.wait(timeout=0.01):
            break
    if stop_event.is_set():
        return

    print("display_video_and_gaze starts.")
    while not stop_event.is_set():
        try:
            if tracker.first_media_ts and tracker.playback_ready_time_ms:
                video_frame = video_queue.peek()
                elapsed_ms = video_frame.get_timestamp() - tracker.first_media_ts

                if elapsed_ms < 0:
                    # Skip video frame that appears earlier than audio.
                    video_queue.get()
                elif (
                    elapsed_ms + tracker.audio_output_latency_ms
                    <= tracker.playback_ready_time_ms
                ):
                    video_queue.get()  # Really take the frame out

                    # Draw gaze on video frame
                    frame_buffer = video_frame.get_buffer()
                    frame_buffer = cv2.resize(
                        frame_buffer, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA
                    )
                    gaze = find_gaze_near_frame(gaze_queue, video_frame.get_timestamp())
                    center = (
                        int(gaze.combined.gaze_2d.x / 2),
                        int(gaze.combined.gaze_2d.y / 2),
                    )
                    radius = 15
                    bgr_color = (255, 255, 0)
                    thickness = 3
                    cv2.circle(frame_buffer, center, radius, bgr_color, thickness)

                    cv2.imshow('Press "q" to exit', frame_buffer)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                stop_event.set()  # Signal all threads to stop
                break
        except queue.Empty:
            continue


def find_gaze_near_frame(queue, timestamp):
    item = queue.get()
    if item.get_timestamp() > timestamp:
        return item

    while True:
        if queue.empty():
            return item
        else:
            next_item = queue.get_nowait()
            if next_item.get_timestamp() > timestamp:
                return next_item
            item = next_item


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

    mode = StreamingMode.GAZE | StreamingMode.AUDIO_VIDEO
    th = sc.create_streaming_thread(mode, update_audio_stream)
    th.start()

    audio_queue = PeekableQueue()
    video_queue = PeekableQueue()
    gaze_queue = PeekableQueue()
    start_event = threading.Event()
    stop_event = threading.Event()

    tracker = PlaybackTimingTracker(start_event, audio_streams)

    # Create and start threads for audio and video playback
    play_audio_thread = threading.Thread(
        target=play_audio,
        args=(audio_streams, audio_queue, start_event, tracker, stop_event),
    )
    display_video_gaze_thread = threading.Thread(
        target=display_video_and_gaze,
        args=(video_queue, gaze_queue, start_event, tracker, stop_event),
    )
    play_audio_thread.start()
    display_video_gaze_thread.start()

    try:
        while not stop_event.is_set():
            frames = sc.get_av_frames_from_streaming(timeout=0.5)
            if frames:
                for frame_datum in frames:
                    if isinstance(frame_datum, AudioFrame):
                        audio_queue.put(frame_datum)
                        tracker.update_on_data(frame_datum)
                    elif isinstance(frame_datum, VideoFrame):
                        video_queue.put(frame_datum)

            gazes = sc.get_gazes_from_streaming(timeout=0.5)
            if gazes:
                for gaze in gazes:
                    gaze_queue.put(gaze)

    except KeyboardInterrupt:  # Press Ctrl-C to stop
        stop_event.set()
    except Exception as ex:
        print(ex)
    finally:
        # Wait for threads to finish
        play_audio_thread.join()
        display_video_gaze_thread.join()
        print("All threads joined")

        th.cancel()
        print("th.cancel() called")
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
