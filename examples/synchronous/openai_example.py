import base64
import io
import tempfile
import sys

import sys
import os

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.streaming.gaze_stream import GazeData
from ganzin.sol_sdk.synchronous.models import StreamingMode
from ganzin.sol_sdk.synchronous.sync_client import SyncClient
from ganzin.sol_sdk.utils import find_nearest_timestamp_match

import cv2
from openai import OpenAI
from pydub import AudioSegment
from pydub.playback import play

# Enter your OpenAI API key here
OPENAI_API_KEY = ""


class OpenAICost:
    date_updated = "2025-06-30"
    "Cost $ per 1M token"
    model = {
        "gpt-3.5-turbo": {
            "input_cost": 10,
            "output_cost": 30,
            "neon_frame_input": 0.00765,
        },
        "gpt-4o": {
            "input_cost": 5,
            "output_cost": 15,
            "neon_frame_input": 0.003825,
        },
        "gpt-4-turbo": {
            "input_cost": 10,
            "output_cost": 30,
            "neon_frame_input": 0.00765,
        },
        "tts-1": {"output_cost": 15},
        "tts-1-hd": {"output_cost": 30},
    }

    @classmethod
    def input_cost(cls, model):
        if model in cls.model and "input_cost" in cls.model[model]:
            return cls.model[model]["input_cost"]
        else:
            return None

    @classmethod
    def output_cost(cls, model):
        if model in cls.model and "output_cost" in cls.model[model]:
            return cls.model[model]["output_cost"]
        else:
            return None

    @classmethod
    def frame_cost(cls, model):
        if model in cls.model and "neon_frame_input" in cls.model[model]:
            return cls.model[model]["neon_frame_input"]
        else:
            return None


class Assistant:
    def __init__(self):
        self.address, self.port = get_ip_and_port()
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = "gpt-4o"  # "gpt-4-turbo"
        self.setup_prompts()
        self.mode = "describe"
        self.running = True
        self.key_actions = {
            ord("a"): lambda: setattr(self, "mode", "describe"),
            ord("s"): lambda: setattr(self, "mode", "dangers"),
            ord("d"): lambda: setattr(self, "mode", "intention"),
            ord("f"): lambda: setattr(self, "mode", "in_detail"),
            ord("q"): lambda: self.stop_running(),
            32: self.handle_space,
            27: lambda: setattr(self, "running", False),
        }
        self.session_cost = 0
        self.initialise_device()

    def initialise_device(self):
        print("Looking for the next best device...")
        self.sc = SyncClient(self.address, self.port)
        self.th = self.sc.create_streaming_thread(StreamingMode.GAZE_SCENE)
        self.th.start()
        # self.device = discover_one_device(max_search_duration_seconds=10)
        # if self.device is None:
        #     print("No device found.")
        #     raise SystemExit(-1)

        print(f"Connecting to {self.sc}...")

    def setup_prompts(self):
        self.prompts = {
            "base": "You are a visual and communication aid for individuals with visual impairment (low vision) or communication difficulties, they are wearing eye-tracking glasses, I am sending you an image with a blue circle indicating the wearer's gaze, do not describe the whole image unless explicitly asked, be succinct",
            "describe": "in couple of words (max. 8) say what the person is looking at.",
            "dangers": "briefly indicate if there is any posing risk for the person in the scene, be succinct (max 30 words).",
            "intention": "given that the wearer has mobility and speaking difficulties, briefly try to infer the wearer's intention based on what they are looking at (maximum of 30 words).",
            "in_detail": "describe the scene in detail, with a maximum duration of one minute of speaking.",
        }

    def process_frame(self):
        frame_data = self.sc.get_video_frames_from_streaming(timeout=100.0)
        if frame_data:
            frame_datum = frame_data[-1]  # get the last frame
            self.buffer = frame_datum.get_buffer()
            self.buffer = cv2.resize(
                self.buffer, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA
            )

            gazes = self.sc.get_gazes_from_streaming(timeout=10.0)
            self.gaze = find_nearest_timestamp_match(frame_datum.get_timestamp(), gazes)

            # self.matched = (
            #     self.device.receive_matched_scene_and_eyes_video_frames_and_gaze()
            # )
            # if not self.matched:
            #     print("Not able to find a match!")
            #     return
            self.annotate_and_show_frame()

    def annotate_and_show_frame(self):
        cv2.circle(
            self.buffer,
            (
                int(self.gaze.combined.gaze_2d.x / 2),
                int(self.gaze.combined.gaze_2d.y / 2),
            ),
            radius=20,
            color=(255, 255, 0),
            thickness=3,
        )
        self.buffer = cv2.putText(
            self.buffer,
            str(self.mode),
            (20, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (255, 255, 255),
            2,
            cv2.LINE_8,
        )
        cv2.imshow(
            "Scene camera with eyes and gaze overlay",
            self.buffer,
        )
        key = cv2.waitKey(1) & 0xFF
        if key in self.key_actions:
            self.key_actions[key]()

        # cv2.circle(
        #     self.matched.scene.bgr_pixels,
        #     (int(self.matched.gaze.x), int(self.matched.gaze.y)),
        #     radius=40,
        #     color=(0, 0, 255),
        #     thickness=5,
        # )
        # self.bgr_pixels = self.matched.scene.bgr_pixels
        # self.bgr_pixels = cv2.putText(
        #     self.bgr_pixels,
        #     str(self.mode),
        #     (20, 50),
        #     cv2.FONT_HERSHEY_SIMPLEX,
        #     1.5,
        #     (255, 255, 255),
        #     2,
        #     cv2.LINE_8,
        # )
        # cv2.imshow(
        #     "Scene camera with eyes and gaze overlay",
        #     self.bgr_pixels,
        # )
        # key = cv2.waitKey(1) & 0xFF
        # if key in self.key_actions:
        #     self.key_actions[key]()

    def encode_image(self):
        _, buffer = cv2.imencode(".jpg", self.buffer)
        self.base64Frame = base64.b64encode(buffer).decode("utf-8")

    def assist(self):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": self.prompts["base"] + self.prompts[self.mode],
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        "Here goes the image",
                        {"image": self.base64Frame, "resize": 768},
                    ],
                },
            ],
            max_tokens=200,
        )
        response_cost = (
            response.usage.prompt_tokens / int(1e6) * OpenAICost.input_cost(self.model)
            + response.usage.completion_tokens
            / int(1e6)
            * OpenAICost.output_cost(self.model)
            + OpenAICost.frame_cost(self.model)
        )
        response_audio = self.client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=response.choices[0].message.content,
        )
        TTS_cost = (
            len(response.choices[0].message.content)
            / int(1e6)
            * OpenAICost.output_cost("tts-1")
        )
        self.session_cost += response_cost + TTS_cost
        print(
            f"R: {response.choices[0].message.content}, approx cost(GPT/TTS): {response_cost} / {TTS_cost} $ Total: {response_cost+TTS_cost} $"
        )
        byte_stream = io.BytesIO(response_audio.content)
        audio = AudioSegment.from_file(byte_stream, format="mp3")
        audio = audio.speedup(playback_speed=1.1)
        play(audio)

    def handle_space(self):
        self.encode_image()
        self.assist()

    def stop_running(self):
        self.running = False
        self.th.cancel()
        self.th.join()
        cv2.destroyAllWindows()

    def run(self):
        while self.sc is not None and self.running:
            self.process_frame()
        print("Stopping...")
        print(f"Total session cost {self.session_cost}$")


if __name__ == "__main__":
    eyes = Assistant()
    eyes.run()
