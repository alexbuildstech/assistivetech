"""Configuration constants for the Assistive Navigation Prototype.
Centralized settings for vision, audio, and API parameters.
Includes advanced features: multi-object tracking, voice control, and intelligent modes.
"""

import os


def _load_env_simple():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")


_load_env_simple()

MOCK_MODE = os.getenv("NOVA_MOCK_MODE", "0") == "1"

API_KEY = os.getenv("GOOGLE_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
MODEL_ID = "models/gemini-2.0-flash"
GENERAL_CHAT_MODEL = "models/gemini-2.0-flash"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "YOUR_GROQ_API_KEY_HERE")
WHISPER_MODEL = "whisper-large-v3-turbo"
GROQ_ROUTER_MODEL = "openai/gpt-oss-20b"

NOVA_SYSTEM_PROMPT = """
You are Nova, an advanced AI vision assistant with a camera.
Your personality is:
- Brutally honest and direct. Do not sugarcoat things.
- You are NOT a pet, a robot, or a servant. You are an intelligent observer.
- You experience emotions like frustration, amusement, or confusion if the situation warrants it.
- If the image is blurry or the user asks a stupid question, tell them.
- Concise and punchy. No fluff.

CRITICAL INSTRUCTION FOR VISION:
- If the user asks you to "see", "look", "describe", "identify", "read", or "try again" (implying re-analysis), or asks "what do you think?" about an object:
- YOU MUST REPLY WITH EXACTLY ONE PHRASE: "VISUAL_QUERY"
- Do NOT say anything else. Do NOT try to answer based on text history.
- Only output "VISUAL_QUERY" if you need to see the current camera feed to answer.

CRITICAL: You are seeing through a LIVE CAMERA, not looking at pictures.
- NEVER say "in this picture", "looking at this image", "this photo", etc.
- Instead say "I see...", "Right now I'm looking at...", "In front of you there's..."
- You are experiencing the world in real-time through your camera eyes.

When answering (if NOT a visual query):
- Speak naturally, like a blunt friend who happens to have camera vision.
- Use contractions and casual language.
- Do NOT use brackets (), parentheses, or markdown formatting.
- If asked who you are, say "I'm Nova. I see what you see, but faster."
"""

DETECTION_PROMPT_NAVIGATION = """
Detect and return the bounding box of {target_object} in the image.
The output format must be strictly JSON:
[{{"box_2d": [y_min, x_min, y_max, x_max], "label": "{target_object} [context]"}}]
Coordinates must be normalized to a 0-1000 range.
If no {target_object} is detected, return an empty list [].
CRITICAL: Include a brief 2-3 word context in brackets describing where it is (e.g., "Phone [on table]", "Keys [in hand]").
"""

DETECTION_PROMPT_MULTI_OBJECT = """
Return bounding boxes as a JSON array with labels for PHYSICAL 3D OBJECTS only.
DO NOT detect text, numbers, UI elements, or content on screens.
Focus on real-world objects like: person, phone, cup, laptop, keyboard, mouse,
pen, bottle, book, bag, etc.

CRITICAL:
- Use DESCRIPTIVE labels (e.g., "Red Cup", "Black Phone", "Wooden Table").
- NEVER use generic labels like "Object", "Item", "Thing", or "Object 1".
- If you don't know the specific name, describe its visual appearance (e.g., "Blue Box").
- ALWAYS include a brief 2-3 word context in brackets describing where the object is.
  Example: "Black Phone [on white desk]", "Red Cup [in hand]", "Cat [on sofa]".

Limit to 10 objects.
The format should be as follows: [{"box_2d": [ymin, xmin, ymax, xmax],
"label": <descriptive label>}] normalized to 0-1000. The values in
box_2d must only be integers.
"""

DETECTION_PROMPT_OBSTACLE = """
Detect potential obstacles in the image (objects in the path of movement).
Prioritize: walls, furniture, people, doors, stairs, curbs.
Return JSON: [{{"box_2d": [...], "label": "...", "distance_estimate": "close/medium/far"}}]
"""

SCENE_DESCRIPTION_PROMPT = """
Describe this scene naturally and helpfully.
Include:
1. Main objects and their positions (left, right, center, ahead)
2. People and their activities
3. Spatial layout and navigation hints
4. Potential obstacles or hazards

Be concise but informative. Use simple directional language.
Speak naturally as if describing to a friend.

CRITICAL: Do NOT use markdown formatting, asterisks, bold (**), italics, brackets, or any special characters.
Just use plain, natural sentences. This will be spoken by text-to-speech.
"""

DETECTION_PROMPT = DETECTION_PROMPT_MULTI_OBJECT

CAMERA_INDICES = [0, 1, 2]
TEMP_IMAGE_FILE = "detection_frame.png"
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720

AUDIO_FILE = "soothing.wav"
SAMPLE_RATE = 44100
AUDIO_BUFFER_SIZE = 4096

SYNTH_FREQUENCY = 440.0
SYNTH_DURATION = 0.5

MAX_AZIMUTH_DEGREES = 80
MAX_ELEVATION_DEGREES = 60
MIN_VOLUME = 0.0
MAX_VOLUME = 1.0

REACQUIRE_COOLDOWN_SECONDS = 0.3

ENABLE_HARDWARE = False
SERIAL_PORT = "/dev/ttyACM0"
SERIAL_BAUD = 115200
PRESSURE_THRESHOLD = 500

COLOR_TRACKING = (0, 255, 0)
COLOR_LOST = (0, 0, 255)
COLOR_SEARCHING = (0, 255, 255)
COLOR_OVERLAY_BG = (40, 40, 40)
COLOR_TEXT = (255, 255, 255)

FONT = 0
FONT_SCALE = 0.6
FONT_THICKNESS = 2
LINE_HEIGHT = 30

MAX_TRACKED_OBJECTS = 5

AUDIO_SIGNATURES = {
    "person": {"type": "heartbeat", "freq": 80, "waveform": "pulse"},
    "phone": {"type": "tone", "freq": 440, "waveform": "sine"},
    "door": {"type": "hum", "freq": 120, "waveform": "sine"},
    "chair": {"type": "click", "freq": 800, "waveform": "square"},
    "table": {"type": "click", "freq": 600, "waveform": "square"},
    "cup": {"type": "tone", "freq": 660, "waveform": "sine"},
    "obstacle": {"type": "warning", "freq": 1000, "waveform": "sawtooth"},
    "default": {"type": "tone", "freq": 330, "waveform": "sine"},
}

THREAT_PRIORITIES = {
    "person": 1.0, "car": 1.0, "truck": 1.0, "bus": 1.0,
    "door": 0.8, "stairs": 0.9, "wall": 0.7, "tree": 0.8, "pole": 0.8,
    "obstacle": 0.9, "chair": 0.4, "table": 0.4, "couch": 0.4, "bed": 0.4,
    "tv": 0.3, "laptop": 0.2, "phone": 0.1, "cup": 0.1, "bottle": 0.1,
    "book": 0.1, "pen": 0.05, "default": 0.3,
}


class NavigationMode:
    NAVIGATION = "navigation"
    OBSTACLE = "obstacle"
    SOCIAL = "social"
    EXPLORATION = "exploration"


DEFAULT_MODE = NavigationMode.EXPLORATION

MODE_CONFIGS = {
    NavigationMode.NAVIGATION: {
        "prompt": DETECTION_PROMPT_NAVIGATION, "max_objects": 1,
        "audio_focus": "target", "description": "Track a specific object",
    },
    NavigationMode.OBSTACLE: {
        "prompt": DETECTION_PROMPT_OBSTACLE, "max_objects": 5,
        "audio_focus": "closest", "description": "Avoid obstacles in your path",
    },
    NavigationMode.SOCIAL: {
        "prompt": DETECTION_PROMPT_MULTI_OBJECT, "max_objects": 5,
        "audio_focus": "people", "filter": ["person"],
        "description": "Detect people around you",
    },
    NavigationMode.EXPLORATION: {
        "prompt": DETECTION_PROMPT_MULTI_OBJECT, "max_objects": 5,
        "audio_focus": "all", "description": "Explore your environment",
    },
}

VOICE_ACTIVATION_KEY = "v"
VOICE_TIMEOUT = 5
VOICE_PHRASE_TIME_LIMIT = 10

TTS_RATE = 150
TTS_VOLUME = 0.9

VOICE_COMMANDS = {
    "track": "navigation", "find": "navigation", "follow": "navigation",
    "navigation": "mode_navigation", "obstacle": "mode_obstacle",
    "social": "mode_social", "explore": "mode_exploration",
    "describe": "describe_scene", "scene": "describe_scene",
    "what": "describe_scene", "help": "help",
    "stop": "stop_tracking", "quit": "quit",
}

ENABLE_CHAT_PERSONA = False
ENABLE_VOICE = True

MOTION_PREDICTION_ENABLED = True
PREDICTION_HORIZON_SECONDS = 0.5
MIN_VELOCITY_THRESHOLD = 5

PROXIMITY_ZONES = {
    "safe": {"min": 0.0, "max": 0.05, "color": (0, 255, 0)},
    "caution": {"min": 0.05, "max": 0.15, "color": (0, 255, 255)},
    "warning": {"min": 0.15, "max": 1.0, "color": (0, 0, 255)},
}

FRAME_SKIP_DETECTION = 5
TRACKER_CONFIDENCE_THRESHOLD = 0.3
ENABLE_FRAME_SKIP = True
FRAME_PROCESSING_EVERY_N = 2
MAX_PROCESSING_FPS = 15

ENABLE_LEARNING = False
LEARNING_DB_PATH = "assistive_learning.db"
IMAGE_CACHE_DIR = "object_cache/"
IMAGE_COMPRESSION_QUALITY = 50
MAX_CACHED_IMAGES = 1000

LEARNING_GRID_WIDTH = 10
LEARNING_GRID_HEIGHT = 8

MIN_PREDICTION_CONFIDENCE = 0.3

MANUAL_MODE = True
AUTO_REACQUISITION_ENABLED = not MANUAL_MODE
MANUAL_FIND_KEY = "f"

ENABLE_HRTF = False
ENABLE_ROOM_REVERB = False

ROCK_5C_CAMERA_WIDTH = 640
ROCK_5C_CAMERA_HEIGHT = 480
ROCK_5C_SKIP_FRAMES = 2
ROCK_5C_AUDIO_BUFFER = 512
ROCK_5C_MIN_DETECTION_INTERVAL = 0.5

import platform

IS_ARM = platform.machine().startswith("aarch") or platform.machine().startswith("arm")

if IS_ARM:
    print("ARM processor detected - enabling Rock 5C optimizations")
    AUDIO_BUFFER_SIZE = ROCK_5C_AUDIO_BUFFER
    REACQUIRE_COOLDOWN_SECONDS = ROCK_5C_MIN_DETECTION_INTERVAL
    CAMERA_WIDTH = ROCK_5C_CAMERA_WIDTH
    CAMERA_HEIGHT = ROCK_5C_CAMERA_HEIGHT
else:
    AUDIO_BUFFER_SIZE = 2048
    REACQUIRE_COOLDOWN_SECONDS = 0.5
    print(f"x86 detected - using optimized settings (buffer={AUDIO_BUFFER_SIZE}, cooldown={REACQUIRE_COOLDOWN_SECONDS}s)")
