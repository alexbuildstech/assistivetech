"""Configuration constants for the Assistive Navigation Prototype.
Centralized settings for vision, audio, and API parameters.
Includes patent-worthy features: multi-object tracking, voice control, and intelligent modes.
"""

import os

# ============================================================================
# GEMINI API CONFIGURATION
# ============================================================================
API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
MODEL_ID = "models/gemini-flash-lite-latest"  # Reverted to 2.0 Flash as requested
GENERAL_CHAT_MODEL = "models/gemini-flash-lite-latest"  # For general conversation

# ============================================================================
# GROQ API CONFIGURATION (for advanced Whisper STT & Routing)
# ============================================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "YOUR_API_KEY_HERE")
WHISPER_MODEL = "whisper-large-v3-turbo"
GROQ_ROUTER_MODEL = "openai/gpt-oss-20b"  # Intelligent router model

# Nova Persona Definition
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

# Detection prompts (dynamically selected based on mode)
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

# ============================================================================
# CAMERA CONFIGURATION
# ============================================================================
CAMERA_INDICES = [ 2]  # Try these camera indices in order
TEMP_IMAGE_FILE = "detection_frame.png"

# ============================================================================
# AUDIO CONFIGURATION
# ============================================================================
AUDIO_FILE = "soothing.wav"
SAMPLE_RATE = 44100
AUDIO_BUFFER_SIZE = 4096

# Fallback: Generate a synthetic tone if audio file is missing
SYNTH_FREQUENCY = 440.0  # A4 note in Hz
SYNTH_DURATION = 0.5  # seconds

# ============================================================================
# SPATIAL MAPPING CONFIGURATION
# ============================================================================
# Maximum angle for horizontal deviation (left/right)
MAX_AZIMUTH_DEGREES = 80

# Maximum angle for vertical deviation (up/down)
MAX_ELEVATION_DEGREES = 60

# Volume range based on object size/distance
MIN_VOLUME = 0.0
MAX_VOLUME = 1.0

# ============================================================================
# RE-ACQUISITION CONFIGURATION
# ============================================================================
# Cooldown between re-acquisition attempts to avoid API spam (OPTIMIZED for i3 hardware)
REACQUIRE_COOLDOWN_SECONDS = 0.3  # Aggressive for lower latency

# ============================================================================
# VISUAL DEBUG OVERLAY CONFIGURATION
# ============================================================================
# Colors (BGR format for OpenCV)
COLOR_TRACKING = (0, 255, 0)      # Green
COLOR_LOST = (0, 0, 255)          # Red
COLOR_SEARCHING = (0, 255, 255)   # Yellow
COLOR_OVERLAY_BG = (40, 40, 40)   # Dark gray
COLOR_TEXT = (255, 255, 255)      # White

# UI settings
FONT = 0  # cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.6
FONT_THICKNESS = 2
LINE_HEIGHT = 30

# ============================================================================
# MULTI-OBJECT TRACKING CONFIGURATION
# ============================================================================
MAX_TRACKED_OBJECTS = 5  # Limit to prevent auditory overload

# Audio signature mapping (frequency in Hz for each object type)
AUDIO_SIGNATURES = {
    "person": {"type": "heartbeat", "freq": 80, "waveform": "pulse"},
    "phone": {"type": "tone", "freq": 440, "waveform": "sine"},  # A4 note
    "door": {"type": "hum", "freq": 120, "waveform": "sine"},
    "chair": {"type": "click", "freq": 800, "waveform": "square"},
    "table": {"type": "click", "freq": 600, "waveform": "square"},
    "cup": {"type": "tone", "freq": 660, "waveform": "sine"},  # E5 note
    "obstacle": {"type": "warning", "freq": 1000, "waveform": "sawtooth"},
    "default": {"type": "tone", "freq": 330, "waveform": "sine"},  # E4 note
}

# Semantic Threat Priorities (0.0 - 1.0)
# Higher value = Higher priority for audio focus and collision warning
THREAT_PRIORITIES = {
    "person": 1.0,
    "car": 1.0,
    "truck": 1.0,
    "bus": 1.0,
    "door": 0.8,
    "stairs": 0.9,
    "wall": 0.7,
    "tree": 0.8,
    "pole": 0.8,
    "obstacle": 0.9,
    "chair": 0.4,
    "table": 0.4,
    "couch": 0.4,
    "bed": 0.4,
    "tv": 0.3,
    "laptop": 0.2,
    "phone": 0.1,
    "cup": 0.1,
    "bottle": 0.1,
    "book": 0.1,
    "pen": 0.05,
    "default": 0.3
}

# ============================================================================
# INTELLIGENT MODE CONFIGURATION
# ============================================================================
class NavigationMode:
    NAVIGATION = "navigation"      # Track specific target
    OBSTACLE = "obstacle"          # Avoid obstacles
    SOCIAL = "social"              # Track people
    EXPLORATION = "exploration"    # Describe environment

DEFAULT_MODE = NavigationMode.EXPLORATION  # Start in exploration mode to detect all objects

# Mode-specific settings
MODE_CONFIGS = {
    NavigationMode.NAVIGATION: {
        "prompt": DETECTION_PROMPT_NAVIGATION,
        "max_objects": 1,
        "audio_focus": "target",
        "description": "Track a specific object"
    },
    NavigationMode.OBSTACLE: {
        "prompt": DETECTION_PROMPT_OBSTACLE,
        "max_objects": 5,
        "audio_focus": "closest",
        "description": "Avoid obstacles in your path"
    },
    NavigationMode.SOCIAL: {
        "prompt": DETECTION_PROMPT_MULTI_OBJECT,
        "max_objects": 5,
        "audio_focus": "people",
        "filter": ["person"],  # Only track people
        "description": "Detect people around you"
    },
    NavigationMode.EXPLORATION: {
        "prompt": DETECTION_PROMPT_MULTI_OBJECT,
        "max_objects": 5,
        "audio_focus": "all",
        "description": "Explore your environment"
    },
}

# ============================================================================
# VOICE CONTROL CONFIGURATION
# ============================================================================
VOICE_ACTIVATION_KEY = 'v'  # Press 'V' to activate voice input
VOICE_TIMEOUT = 5  # Seconds to wait for voice command
VOICE_PHRASE_TIME_LIMIT = 10  # Max seconds for a single phrase

# Text-to-speech settings
TTS_RATE = 150  # Words per minute
TTS_VOLUME = 0.9  # 0.0 to 1.0

# Voice commands mapping
VOICE_COMMANDS = {
    # Object tracking
    "track": "navigation",
    "find": "navigation",
    "follow": "navigation",
    
    # Mode switching
    "navigation": "mode_navigation",
    "obstacle": "mode_obstacle",
    "social": "mode_social",
    "explore": "mode_exploration",
    
    # Actions
    "describe": "describe_scene",
    "scene": "describe_scene",
    "what": "describe_scene",
    "help": "help",
    "stop": "stop_tracking",
    "quit": "quit",
}

# ============================================================================
# PREDICTIVE TRACKING CONFIGURATION
# ============================================================================
MOTION_PREDICTION_ENABLED = True
PREDICTION_HORIZON_SECONDS = 0.5  # Predict 0.5 seconds ahead
MIN_VELOCITY_THRESHOLD = 5  # pixels/frame to consider as "moving"

# ============================================================================
# PROXIMITY ALERT CONFIGURATION
# ============================================================================
PROXIMITY_ZONES = {
    "safe": {"min": 0.0, "max": 0.3, "color": (0, 255, 0)},      # >30% of frame
    "caution": {"min": 0.3, "max": 0.6, "color": (0, 255, 255)}, # 30-60%
    "warning": {"min": 0.6, "max": 1.0, "color": (0, 0, 255)},   # <60%
}

# ============================================================================
# PERFORMANCE OPTIMIZATION
# ============================================================================
FRAME_SKIP_DETECTION = 10  # Optimized for i3 10th gen (more frequent checks)
TRACKER_CONFIDENCE_THRESHOLD = 0.5  # Re-acquire if tracker confidence drops below this

# ============================================================================
# SELF-LEARNING SYSTEM CONFIGURATION
# ============================================================================
ENABLE_LEARNING = True
LEARNING_DB_PATH = "assistive_learning.db"
IMAGE_CACHE_DIR = "object_cache/"
IMAGE_COMPRESSION_QUALITY = 50  # JPEG quality (0-100)
MAX_CACHED_IMAGES = 1000

# Room mapping grid (divide frame into NxM cells)
LEARNING_GRID_WIDTH = 10
LEARNING_GRID_HEIGHT = 8

# Prediction thresholds
MIN_PREDICTION_CONFIDENCE = 0.3  # Only use prediction if >30% confidence

# ============================================================================
# MANUAL DETECTION MODE
# ============================================================================
MANUAL_MODE = True  # Requires user to press 'F' to trigger detection
AUTO_REACQUISITION_ENABLED = not MANUAL_MODE  # Auto-reacquire only if not manual

# Manual mode UI
MANUAL_FIND_KEY = 'f'  # Key to trigger manual detection

# ============================================================================
# HRTF SPATIAL AUDIO
# ============================================================================
ENABLE_HRTF = True  # Use advanced HRTF audio instead of basic stereo
ENABLE_ROOM_REVERB = True  # Simple room acoustics simulation

# ============================================================================
# ROCK 5C / ARM SBC OPTIMIZATION
# ============================================================================
# Optimizations for low-latency performance on ARM single-board computers

# Camera resolution (lower = faster)
ROCK_5C_CAMERA_WIDTH = 640  # Default: 640 (vs 1280)
ROCK_5C_CAMERA_HEIGHT = 480  # Default: 480 (vs 720)

# Frame processing
ROCK_5C_SKIP_FRAMES = 2  # Process every Nth frame (2 = 30fps → 15fps processing)

# Audio buffer (smaller = lower latency, but may cause glitches) - OPTIMIZED
ROCK_5C_AUDIO_BUFFER = 2048  # Reduced from 4096 for lower latency

# Detection rate limiting
ROCK_5C_MIN_DETECTION_INTERVAL = 1.0  # Aggressive for faster response

# Enable optimizations automatically if running on ARM
import platform
IS_ARM = platform.machine().startswith('aarch') or platform.machine().startswith('arm')

if IS_ARM:
    print("🚀 ARM processor detected - enabling Rock 5C optimizations")
    # Override settings for performance
    AUDIO_BUFFER_SIZE = ROCK_5C_AUDIO_BUFFER
    REACQUIRE_COOLDOWN_SECONDS = ROCK_5C_MIN_DETECTION_INTERVAL
else:
    # For x86/desktop (i3 10th gen), optimize for lowest latency
    AUDIO_BUFFER_SIZE = 2048  # Balanced - reduced from aggressive 1024 to prevent underflows
    print(f"💻 x86 detected - using optimized settings (buffer={AUDIO_BUFFER_SIZE})")
