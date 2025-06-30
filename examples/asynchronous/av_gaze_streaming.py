"""
This Python file demonstrates how to play streaming audio, video, and gaze
in sync using timestamps.

It serves as an example for synchronizing playback of audio, video, and gaze
streams, ensuring all media types are played together in real time according
to their respective timestamps.
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
from ganzin.sol_sdk.asynchronous.async_client import AsyncClient, recv_av, recv_gaze
from ganzin.sol_sdk.common_models import Camera
from ganzin.sol_sdk.streaming.audio_config import AudioConfig
from ganzin.sol_sdk.streaming.audio_frame import AudioFrame
from ganzin.sol_sdk.streaming.video_frame import VideoFrame

# Constants
MILLISECONDS_PER_SECOND = 1000
BUFFER_DURATION_MS = 800


class PeekableQueue(asyncio.Queue):
    async def peek(self):
        while self.empty():  # Wait until the queue has something
            await asyncio.sleep(0)
        return self._queue[0]


class PlaybackTimingTracker:
    def __init__(self, start_play_event: asyncio.Event, audio_streams):
        self.start_play_event = start_play_event
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
            self.start_play_event.set()
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


async def collect_audio_video(
    ac: AsyncClient,
    audio_queue,
    video_queue,
    update_audio_stream,
    tracker: PlaybackTimingTracker,
    stop_event,
):
    try:
        async for frame_data in recv_av(ac, Camera.SCENE, update_audio_stream):
            if isinstance(frame_data, AudioFrame):
                await audio_queue.put(frame_data)
                tracker.update_on_data(frame_data)
            elif isinstance(frame_data, VideoFrame):
                await video_queue.put(frame_data)

            if stop_event.is_set():
                break
    except Exception as ex:
        print(f"Error occurred: {ex}")


async def collect_gaze(ac: AsyncClient, gaze_queue, stop_event):
    async for gaze in recv_gaze(ac):
        await gaze_queue.put(gaze)

        if stop_event.is_set():
            break


async def display_video_and_gaze(
    video_queue: PeekableQueue,
    gaze_queue,
    tracker: PlaybackTimingTracker,
    start_play_event: asyncio.Event,
    timeout,
    stop_event,
):
    await start_play_event.wait()
    while not stop_event.is_set():
        try:
            if tracker.first_media_ts and tracker.playback_ready_time_ms:
                video_frame = await video_queue.peek()
                elapsed_ms = video_frame.get_timestamp() - tracker.first_media_ts

                if elapsed_ms < 0:
                    # Skip video frame that appears earlier than audio.
                    await video_queue.get()
                elif (
                    elapsed_ms + tracker.audio_output_latency_ms
                    <= tracker.playback_ready_time_ms
                ):
                    await video_queue.get()  # Really take the frame out

                    # Draw gaze on video frame
                    frame_buffer = video_frame.get_buffer()
                    frame_buffer = cv2.resize(
                        frame_buffer, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA
                    )

                    gaze = await find_gaze_near_frame(
                        gaze_queue, video_frame.get_timestamp(), timeout
                    )
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

            await asyncio.sleep(0)
        except asyncio.TimeoutError:
            continue
        except Exception as ex:
            print("Error occurred: {ex}")


async def find_gaze_near_frame(queue, timestamp, timeout):
    item = await asyncio.wait_for(queue.get(), timeout=timeout)
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


async def forward_asyncio_to_thread_queue(
    audio_queue: PeekableQueue,
    audio_playback_queue: queue.Queue,
    tracker: PlaybackTimingTracker,
    start_play_event: asyncio.Event,
    stop_event,
):
    await start_play_event.wait()
    while not stop_event.is_set():
        if tracker.first_media_ts and tracker.playback_ready_time_ms:
            audio_frame = await audio_queue.peek()
            elapsed_ms = audio_frame.get_timestamp() - tracker.first_media_ts
            if elapsed_ms <= tracker.playback_ready_time_ms:
                await audio_queue.get()  # Really take the element out
                audio_playback_queue.put(audio_frame)
        await asyncio.sleep(0)


def audio_playback_thread(audio_playback_queue: queue.Queue, audio_output, stop_event):
    while not stop_event.is_set():
        try:
            audio_frame = audio_playback_queue.get(timeout=0.1)
            audio_output[0].write(audio_frame.get_pcm())
        except queue.Empty:
            continue


async def main(stop_event):
    TIMEOUT_SECONDS = 5.0

    address, port = get_ip_and_port()
    start_play_event = asyncio.Event()

    audio_queue = PeekableQueue()
    audio_playback_queue = queue.Queue()  # thread-safe
    video_queue = PeekableQueue()
    gaze_queue = asyncio.Queue()

    tasks = None

    audio_streams = [None]
    # Create a callback function that initializes the audio stream when
    # new audio configuration is received. This function updates the stream
    # reference in the audio_streams list.
    update_audio_stream = create_stream_updater(audio_streams)
    play_audio_thread = threading.Thread(
        target=audio_playback_thread,
        args=(audio_playback_queue, audio_streams, stop_event),
    )
    tracker = PlaybackTimingTracker(start_play_event, audio_streams)

    try:
        async with AsyncClient(address, port) as ac:
            if not (await ac.get_status()).audio_enabled:
                print("Warning: Please enable 'Microphone' in the server settings.")
                return

            tasks = [
                asyncio.create_task(
                    collect_audio_video(
                        ac,
                        audio_queue,
                        video_queue,
                        update_audio_stream,
                        tracker,
                        stop_event,
                    )
                ),
                asyncio.create_task(collect_gaze(ac, gaze_queue, stop_event)),
                asyncio.create_task(
                    forward_asyncio_to_thread_queue(
                        audio_queue,
                        audio_playback_queue,
                        tracker,
                        start_play_event,
                        stop_event,
                    )
                ),
                asyncio.create_task(
                    display_video_and_gaze(
                        video_queue,
                        gaze_queue,
                        tracker,
                        start_play_event,
                        TIMEOUT_SECONDS,
                        stop_event,
                    )
                ),
            ]

            print("App running. Press Ctrl+C to stop.")

            play_audio_thread.start()

            # Wait for the stop_event to be set without blocking the event loop
            await asyncio.to_thread(stop_event.wait)

    except KeyboardInterrupt:
        print("Stopping app...")
        stop_event.set()
    finally:
        # Cancel async tasks gracefully
        if tasks:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        if play_audio_thread.is_alive():
            play_audio_thread.join()

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
