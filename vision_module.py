"""
Vision Controller Module for Assistive Navigation.
Handles camera capture, AI-based detection, classical tracking, and self-healing re-acquisition.
"""

import json
import os
import re
import threading
import time
import io
import config

try:
    import cv2
    import numpy as np

    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    np = None
    CV2_AVAILABLE = False

try:
    from tenacity import retry, stop_after_attempt, wait_fixed

    TENACITY_AVAILABLE = True
except ImportError:

    def retry(stop=None, wait=None):
        def decorator(fn):
            return fn

        return decorator

    stop_after_attempt = lambda n: None
    wait_fixed = lambda n: None
    TENACITY_AVAILABLE = False

try:
    from google import genai
    from google.genai import types

    GENAI_AVAILABLE = True
except ImportError as e:
    print(
        f"[ERROR] Missing required library: {e.name}. Please run 'pip install google-genai'"
    )
    genai = None
    types = None
    GENAI_AVAILABLE = False


class _MockGeminiClient:
    """Mock Gemini client for testing without API keys."""

    class _MockResponse:
        def __init__(self, text):
            self.text = text

    def __init__(self):
        self._call_count = 0

    class _MockModels:
        @staticmethod
        def generate_content(model=None, contents=None, config=None):
            prompt_text = ""
            for item in contents or []:
                if isinstance(item, str):
                    prompt_text = item
                    break

            if (
                "Detect and return" in prompt_text
                or "bounding box" in prompt_text.lower()
            ):
                return _MockGeminiClient._MockResponse(
                    '[{"box_2d": [200, 300, 500, 600], "label": "Phone [on desk]"}]'
                )
            elif (
                "PHYSICAL 3D OBJECTS" in prompt_text
                or "Return bounding boxes" in prompt_text
            ):
                return _MockGeminiClient._MockResponse(
                    '[{"box_2d": [100, 200, 400, 500], "label": "Laptop [on table]"}, '
                    '{"box_2d": [300, 600, 600, 800], "label": "Coffee Cup [near laptop]"}, '
                    '{"box_2d": [50, 50, 200, 200], "label": "Person [standing nearby]"}]'
                )
            elif "Describe this scene" in prompt_text:
                return _MockGeminiClient._MockResponse(
                    "I see a desk with a laptop and coffee cup. There's a person standing nearby."
                )
            else:
                return _MockGeminiClient._MockResponse(
                    "I'm Nova. I see what you see, but faster."
                )

    @property
    def models(self):
        return self._MockModels()


class VisionController:
    """
    Manages camera capture, initial object detection via Gemini,
    continuous real-time tracking with CSRT, and self-healing re-acquisition.
    """

    # Pre-allocated encode buffer for JPEG encoding (much faster than PNG)
    _encode_buffer = None
    JPEG_QUALITY = 85  # Good balance between quality and speed

    def __init__(self, camera_index=None):
        """
        Initialize the vision controller.
        """
        # Initialize camera
        self.cap = None
        self._init_camera(camera_index)

        self.frame_height = config.CAMERA_HEIGHT
        self.frame_width = config.CAMERA_WIDTH
        self.tracker = None

        # Re-acquisition state
        self.is_searching = False
        self.search_thread = None
        self.search_result = None
        self.search_lock = threading.Lock()

        if config.MOCK_MODE:
            print("[VISION] MOCK MODE - Using mock Gemini client for testing.")
            self.gemini_client = _MockGeminiClient()
        elif not GENAI_AVAILABLE:
            raise RuntimeError("Google Generative AI library not available.")
        else:
            try:
                self.gemini_client = genai.Client(api_key=config.API_KEY)
                print("[VISION] Gemini client initialized successfully.")
            except Exception as e:
                raise RuntimeError(f"Failed to configure Gemini client. Error: {e}")

        # Active Capture State
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.capture_active = False
        self.capture_thread = None

        # Start capture thread if camera is initialized
        if self.cap and self.cap.isOpened():
            self._start_capture_thread()

    def _init_camera(self, camera_index):
        """
        Robust camera initialization - tries multiple indices if needed.
        """
        indices_to_try = (
            [camera_index] if camera_index is not None else config.CAMERA_INDICES
        )
        if isinstance(indices_to_try, int):
            indices_to_try = [indices_to_try]

        for idx in indices_to_try:
            print(f"[VISION] Trying camera index {idx}...")
            cap = cv2.VideoCapture(idx)

            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    print(f"[VISION] Camera opened successfully at index {idx}")
                    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
                    self.cap = cap
                    return
                else:
                    cap.release()

        print("[ERROR] Could not access any camera. Continuing in headless mode.")
        self.cap = None

    def _start_capture_thread(self):
        """Starts the background frame capture thread."""
        self.capture_active = True
        self.capture_thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.capture_thread.start()
        print("[VISION] Active capture thread started.")

    def _capture_worker(self):
        """Continuously captures frames to ensure zero latency."""
        while self.capture_active and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                with self.frame_lock:
                    self.latest_frame = frame
            else:
                time.sleep(0.01)

    def read_frame(self, wait_timeout=2.0):
        """
        Returns the latest captured frame instantly.
        """
        start_time = time.time()
        while time.time() - start_time < wait_timeout:
            with self.frame_lock:
                if self.latest_frame is not None:
                    return True, self.latest_frame.copy()
            time.sleep(0.01)
        return False, None

    def stop_capture(self):
        """Stops the active capture thread."""
        self.capture_active = False
        if self.capture_thread:
            self.capture_thread.join(timeout=1.0)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def _detect_object_with_gemini(self, frame):
        """
        Sends a single frame to the Gemini model for detection.
        """
        try:
            is_success, buffer = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.JPEG_QUALITY]
            )
            if not is_success:
                return None

            image_bytes = buffer.tobytes()

            response = self.gemini_client.models.generate_content(
                model=config.MODEL_ID,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    config.DETECTION_PROMPT,
                ],
            )

            cleaned_text = self._extract_json(response.text)
            if not cleaned_text:
                return None

            detections = json.loads(cleaned_text)
            if not detections or not isinstance(detections, list):
                return None

            det = detections[0]
            y_min, x_min, y_max, x_max = det["box_2d"]

            x1 = int((x_min / 1000) * self.frame_width)
            y1 = int((y_min / 1000) * self.frame_height)
            x2 = int((x_max / 1000) * self.frame_width)
            y2 = int((y_max / 1000) * self.frame_height)

            return (x1, y1, x2 - x1, y2 - y1)
        except Exception as e:
            print(f"[ERROR] Error during Gemini API call: {e}")
            raise  # Re-raise for tenacity retry

    def _extract_json(self, text):
        """Robustly extract JSON from model response."""
        match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            return match.group(0).strip()
        return text.strip()

    def initialize_tracker(self):
        """
        Captures the first frame and uses Gemini to find the object to track.
        """
        print("[VISION] Capturing initial frame for object detection...")
        ret, frame = self.read_frame()
        if not ret:
            print("[ERROR] Could not read frame.")
            return False

        try:
            bbox = self._detect_object_with_gemini(frame)
        except:
            bbox = None

        if bbox:
            self.reinit_tracker(frame, bbox)
            return True
        return False

    def _async_reacquire_worker(self, frame):
        """Worker function for async re-acquisition."""
        try:
            bbox = self._detect_object_with_gemini(frame)
            with self.search_lock:
                self.search_result = bbox
                self.is_searching = False
        except Exception as e:
            print(f"[ERROR] Re-acquisition worker error: {e}")
            with self.search_lock:
                self.search_result = None
                self.is_searching = False

    def start_reacquisition(self, frame):
        """Initiates async re-acquisition."""
        with self.search_lock:
            if self.is_searching:
                return False
            self.is_searching = True
            self.search_result = None

        self.search_thread = threading.Thread(
            target=self._async_reacquire_worker, args=(frame.copy(),), daemon=True
        )
        self.search_thread.start()
        return True

    def check_reacquisition_result(self):
        """Checks if async re-acquisition has completed."""
        with self.search_lock:
            if self.is_searching:
                return None
            result = self.search_result
            self.search_result = None
        return result

    def track_object(self, frame):
        """Updates the tracker with the provided frame."""
        if self.tracker:
            ok, box = self.tracker.update(frame)
            if ok:
                return True, box
            else:
                self.tracker = None
        return False, None

    def reinit_tracker(self, frame, bbox):
        """Re-initialize the tracker."""
        try:
            if hasattr(cv2, "TrackerCSRT_create"):
                self.tracker = cv2.TrackerCSRT_create()
            elif hasattr(cv2, "legacy"):
                self.tracker = cv2.legacy.TrackerCSRT_create()
            else:
                self.tracker = cv2.TrackerKCF_create()

            self.tracker.init(frame, bbox)
            print(f"🔄 Tracker initialized at {bbox}")
        except Exception as e:
            print(f"❌ Failed to init tracker: {e}")

    def release(self):
        """Releases the camera resource."""
        self.stop_capture()
        if self.cap:
            self.cap.release()

    def _detect_multi_objects_with_gemini(self, frame, prompt):
        """Multi-object detection."""
        try:
            is_success, buffer = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.JPEG_QUALITY]
            )
            if not is_success:
                return []
            image_bytes = buffer.tobytes()
            response = self.gemini_client.models.generate_content(
                model=config.MODEL_ID,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    prompt,
                ],
            )
            cleaned_text = self._extract_json(response.text)
            if not cleaned_text:
                return []
            detections = json.loads(cleaned_text)
            return detections if isinstance(detections, list) else []
        except Exception as e:
            print(f"[ERROR] Multi-detection error: {e}")
            return []

    def start_reacquisition_multi(self, frame, prompt):
        """Async multi-object re-acquisition."""
        with self.search_lock:
            if self.is_searching:
                return False
            self.is_searching = True
            self.search_result = None

        def worker():
            detections = self._detect_multi_objects_with_gemini(frame, prompt)
            with self.search_lock:
                self.search_result = detections
                self.is_searching = False

        self.search_thread = threading.Thread(target=worker, daemon=True)
        self.search_thread.start()
        return True

    def get_scene_description(self, frame):
        """Scene description."""
        try:
            is_success, buffer = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.JPEG_QUALITY]
            )
            if not is_success:
                return None
            image_bytes = buffer.tobytes()
            response = self.gemini_client.models.generate_content(
                model=config.MODEL_ID,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    config.SCENE_DESCRIPTION_PROMPT,
                ],
            )
            return response.text.strip()
        except Exception as e:
            print(f"[ERROR] Scene description error: {e}")
            return None

    def describe_scene(self, frame, voice_controller=None):
        """Async scene description."""

        def worker():
            description = self.get_scene_description(frame)
            if description and voice_controller:
                voice_controller.speak(description, async_mode=True)

        threading.Thread(target=worker, daemon=True).start()

    def ask_about_scene(
        self, frame, question, voice_controller=None, history_context=""
    ):
        """Async Visual Q&A."""

        def worker():
            try:
                is_success, buffer = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.JPEG_QUALITY]
                )
                if not is_success:
                    return
                image_bytes = buffer.tobytes()
                prompt = f"Context: {history_context}\nQuestion: {question}"
                response = self.gemini_client.models.generate_content(
                    model=config.MODEL_ID,
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                        prompt,
                    ],
                )
                answer = response.text.strip()
                if voice_controller:
                    voice_controller.speak(answer, async_mode=True)
            except Exception as e:
                print(f"❌ Q&A error: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def attempt_local_recovery(self, frame, tracked_object):
        """Local recovery via template matching."""
        if tracked_object.template is None:
            return False, None
        try:
            template = tracked_object.template
            h_templ, w_templ = template.shape[:2]
            res = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val > 0.7:
                bbox = (max_loc[0], max_loc[1], w_templ, h_templ)
                return True, bbox
            return False, None
        except:
            return False, None
