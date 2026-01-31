"""
Vision Controller Module for Assistive Navigation.
Handles camera capture, AI-based detection, classical tracking, and self-healing re-acquisition.
"""

import cv2
import json
import numpy as np
import os
import re
import threading
import time
import config

try:
    from google import genai
    from google.genai import types
except ImportError as e:
    print(f"❌ Missing required library: {e.name}. Please run 'pip install google-generativeai'")
    exit()


class VisionController:
    """
    Manages camera capture, initial object detection via Gemini,
    continuous real-time tracking with CSRT, and self-healing re-acquisition.
    """
    
    def __init__(self, camera_index=None):
        """
        Initialize the vision controller.
        
        Args:
            camera_index: Specific camera index, or None to auto-detect.
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
        
        # Initialize Gemini client
        try:
            self.gemini_client = genai.Client(api_key=config.API_KEY)
            print("✅ Gemini client initialized successfully.")
        except Exception as e:
            raise RuntimeError(f"Failed to configure Gemini client. Check API Key. Error: {e}")
        
        print(f"🎥 Camera initialized | Resolution: {self.frame_width}x{self.frame_height}")
    
    def _init_camera(self, camera_index):
        """
        Robust camera initialization - tries multiple indices if needed.
        """
        indices_to_try = [camera_index] if camera_index is not None else config.CAMERA_INDICES
        if isinstance(indices_to_try, int):
            indices_to_try = [indices_to_try]
        
        for idx in indices_to_try:
            print(f"🔍 Trying camera index {idx}...")
            cap = cv2.VideoCapture(idx)
            
            if cap.isOpened():
                # Test read to ensure it actually works
                ret, _ = cap.read()
                if ret:
                    print(f"✅ Camera opened successfully at index {idx}")
                    
                    # OPTIMIZATION: Use MJPG for smoother high-res video
                    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                    
                    # Set resolution to 1280x720 as requested
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    
                    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    print(f"🎥 Resolution set to: {actual_w}x{actual_h} (MJPG)")
                    
                    self.cap = cap
                    return
                else:
                    cap.release()
            
        raise IOError(f"Could not access any camera. Tried indices: {indices_to_try}")
    
    def _detect_object_with_gemini(self, frame):
        """
        Sends a single frame to the Gemini model for detection.
        Returns a bounding box tuple (x, y, w, h) or None if not found.
        """
        import io
        
        try:
            # OPTIMIZATION: Use BytesIO instead of writing to disk
            is_success, buffer = cv2.imencode(".png", frame)
            if not is_success:
                print("❌ Failed to encode frame")
                return None
            
            image_bytes = io.BytesIO(buffer).read()
            
            response = self.gemini_client.models.generate_content(
                model=config.MODEL_ID,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                    config.DETECTION_PROMPT
                ]
            )
            
            # Clean and parse the model's JSON response
            cleaned_text = self._extract_json(response.text)
            if not cleaned_text:
                return None
                
            detections = json.loads(cleaned_text)
            
            if not detections or not isinstance(detections, list):
                return None  # Object not found
            
            det = detections[0]
            y_min, x_min, y_max, x_max = det["box_2d"]
            
            # Use instance dimensions (respecting config)
            x1 = int((x_min / 1000) * self.frame_width)
            y1 = int((y_min / 1000) * self.frame_height)
            x2 = int((x_max / 1000) * self.frame_width)
            y2 = int((y_max / 1000) * self.frame_height)
            
            return (x1, y1, x2 - x1, y2 - y1)
        
        except Exception as e:
            print(f"❌ Error during Gemini API call: {e}")
            return None

    def _extract_json(self, text):
        """Robustlly extract JSON from model response."""
        # Method 1: Markdown block
        match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        
        # Method 2: Direct array/object
        match = re.search(r'\[[\s\S]*\]', text)
        if match:
            return match.group(0).strip()
            
        # Method 3: Clean trim
        return text.strip()
    
    def initialize_tracker(self):
        """
        Captures the first frame and uses Gemini to find the object to track.
        """
        print("📷 Capturing initial frame for object detection...")
        ret, frame = self.cap.read()
        if not ret:
            print("❌ Could not read frame from camera.")
            return False
        
        print(f"🧠 Requesting initial object location from Gemini ({config.MODEL_ID})...")
        bbox = self._detect_object_with_gemini(frame)
        
        if bbox:
            try:
                if hasattr(cv2, 'TrackerCSRT_create'):
                    self.tracker = cv2.TrackerCSRT_create()
                elif hasattr(cv2, 'legacy'):
                    self.tracker = cv2.legacy.TrackerCSRT_create()
                elif hasattr(cv2, 'TrackerKCF_create'):
                    self.tracker = cv2.TrackerKCF_create()
                else:
                    print("❌ No suitable tracker found")
                    return False
                
                self.tracker.init(frame, bbox)
                print(f"✅ Gemini found object. Tracker initialized at {bbox}.")
                return True
            except Exception as e:
                print(f"❌ Tracker init failed: {e}")
                return False
        else:
            print("⚠️ Gemini could not find the target object in the initial frame.")
            return False
    
    def _async_reacquire_worker(self, frame):
        """
        Worker function for async re-acquisition.
        Runs in a separate thread to avoid blocking the main loop.
        """
        try:
            bbox = self._detect_object_with_gemini(frame)
            
            with self.search_lock:
                self.search_result = bbox
                self.is_searching = False
            
            if bbox:
                print(f"✅ Target re-acquired! New tracker will be initialized at {bbox}.")
            else:
                print("...re-acquisition failed, object not found in current frame.")
        except Exception as e:
            print(f"❌ Error in async reacquire worker: {e}")
            with self.search_lock:
                self.search_result = None
                self.is_searching = False
    
    def start_reacquisition(self, frame):
        """
        Initiates async re-acquisition if not already searching.
        Returns True if search was started, False if already in progress.
        """
        with self.search_lock:
            if self.is_searching:
                return False  # Already searching
            
            self.is_searching = True
            self.search_result = None
        
        print(f"🧠 Target lost. Starting async re-acquisition with Gemini ({config.MODEL_ID})...")
        
        # Start search in background thread
        self.search_thread = threading.Thread(
            target=self._async_reacquire_worker,
            args=(frame.copy(),),
            daemon=True
        )
        self.search_thread.start()
        return True
    
    def check_reacquisition_result(self):
        """
        Checks if async re-acquisition has completed and applies the result.
        Returns the result (bbox or detections list) if ready, None otherwise.
        """
        # THREADING FIX: Minimize time holding lock to prevent deadlocks
        with self.search_lock:
            if self.is_searching:
                return None  # Still searching
            
            result = self.search_result
            self.search_result = None  # Clear immediately
        
        # Return result outside of lock context
        return result
    
    def read_frame(self):
        """Reads a frame from the camera."""
        if self.cap:
            return self.cap.read()
        return False, None

    def track_object(self, frame):
        """
        Updates the tracker with the provided frame.
        Returns (tracking_ok, bounding_box)
        """
        if self.tracker:
            ok, box = self.tracker.update(frame)
            if ok:
                return True, box
            else:
                self.tracker = None
                return False, None
        else:
            return False, None
    
    def reinit_tracker(self, frame, bbox):
        """
        Re-initialize the tracker with a new bounding box.
        Used after successful async re-acquisition.
        """
        try:
            if hasattr(cv2, 'TrackerCSRT_create'):
                self.tracker = cv2.TrackerCSRT_create()
            elif hasattr(cv2, 'legacy'):
                self.tracker = cv2.legacy.TrackerCSRT_create()
            elif hasattr(cv2, 'TrackerKCF_create'):
                self.tracker = cv2.TrackerKCF_create()
            else:
                print("❌ No suitable tracker found")
                return

            self.tracker.init(frame, bbox)
            print(f"🔄 Tracker re-initialized at {bbox}")
        except Exception as e:
            print(f"❌ Failed to reinit tracker: {e}")
    
    def release(self):
        """Releases the camera resource."""
        if self.cap:
            self.cap.release()
            print("📷 Camera released.")
    
    # === PATENT-WORTHY ENHANCEMENTS ===
    
    def _detect_multi_objects_with_gemini(self, frame, prompt):
        """
        Sends a frame to Gemini for multi-object detection.
        """
        import io
        
        try:
            is_success, buffer = cv2.imencode(".png", frame)
            if not is_success:
                return []
                
            image_bytes = io.BytesIO(buffer).read()
            
            response = self.gemini_client.models.generate_content(
                model=config.MODEL_ID,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    temperature=0.5,
                    thinking_config=types.ThinkingConfig(thinking_budget=0)
                )
            )
            
            cleaned_text = self._extract_json(response.text)
            if not cleaned_text:
                return []
            
            detections = json.loads(cleaned_text)
            
            if isinstance(detections, list):
                print(f"✅ Detected {len(detections)} objects")
                return detections
            else:
                return []
        
        except Exception as e:
            print(f"❌ Error during Gemini multi-object detection: {e}")
            return []
    
    def _async_reacquire_multi_worker(self, frame, prompt):
        """
        Worker function for async multi-object re-acquisition.
        """
        try:
            detections = self._detect_multi_objects_with_gemini(frame, prompt)
            
            with self.search_lock:
                self.search_result = detections
                self.is_searching = False
            
            if detections:
                print(f"✅ Re-acquired {len(detections)} objects!")
            else:
                print("...re-acquisition failed, no objects found.")
        except Exception as e:
            print(f"❌ Error in async multi-object worker: {e}")
            with self.search_lock:
                self.search_result = []
                self.is_searching = False
    
    def start_reacquisition_multi(self, frame, prompt):
        """
        Initiates async multi-object re-acquisition.
        
        Args:
            frame: Video frame
            prompt: Detection prompt for current mode
        """
        with self.search_lock:
            if self.is_searching:
                return False
            
            self.is_searching = True
            self.search_result = None
        
        print(f"🧠 Starting async multi-object detection with Gemini...")
        
        self.search_thread = threading.Thread(
            target=self._async_reacquire_multi_worker,
            args=(frame.copy(), prompt),
            daemon=True
        )
        self.search_thread.start()
        return True
    
    def get_scene_description(self, frame):
        """
        Get AI description of the entire scene.
        """
        import io
        try:
            is_success, buffer = cv2.imencode(".png", frame)
            if not is_success:
                return None
                
            image_bytes = io.BytesIO(buffer).read()
            
            response = self.gemini_client.models.generate_content(
                model=config.MODEL_ID,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                    config.SCENE_DESCRIPTION_PROMPT
                ]
            )
            
            return response.text.strip()
        
        except Exception as e:
            print(f"❌ Error getting scene description: {e}")
            return None
    
    def _async_describe_worker(self, frame, voice_controller):
        """Worker for async scene description."""
        description = self.get_scene_description(frame)
        if description:
            print(f"\n📖 Scene Description:\n{description}\n")
            if voice_controller:
                voice_controller.speak(description, async_mode=True)
        else:
            if voice_controller:
                voice_controller.speak("I couldn't describe the scene.", async_mode=True)

    def describe_scene(self, frame, voice_controller=None):
        """
        Get scene description asynchronously to prevent freezing.
        """
        threading.Thread(
            target=self._async_describe_worker,
            args=(frame.copy(), voice_controller),
            daemon=True
        ).start()

    def _async_qa_worker(self, frame, question, voice_controller, history_context=""):
        """Worker for async Visual Q&A."""
        import io
        try:
            is_success, buffer = cv2.imencode(".png", frame)
            if not is_success:
                return
                
            image_bytes = io.BytesIO(buffer).read()
            
            # Construct prompt with history
            prompt = f"""
            [Conversation History]
            {history_context}
            
            [Current Question]
            User: {question}
            
            Answer this question about the image. Speak naturally as if talking to a friend. 
            Do NOT use brackets, parentheses, or markdown formatting. Be concise.
            """
            
            response = self.gemini_client.models.generate_content(
                model=config.MODEL_ID,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                    prompt
                ]
            )
            
            answer = response.text.strip()
            
            print(f"\n❓ Question: {question}")
            print(f"💡 Answer: {answer}\n")
            
            if voice_controller:
                voice_controller.speak(answer, async_mode=True)
                
        except Exception as e:
            print(f"❌ Error in Visual Q&A: {e}")
            if voice_controller:
                voice_controller.speak("Sorry, I couldn't answer that.", async_mode=True)

    def ask_about_scene(self, frame, question, voice_controller=None, history_context=""):
        """
        Ask a specific question about the scene asynchronously.
        """
        threading.Thread(
            target=self._async_qa_worker,
            args=(frame.copy(), question, voice_controller, history_context),
            daemon=True
        ).start()

    def attempt_local_recovery(self, frame, tracked_object):
        """
        Attempt to recover a lost object using template matching.
        
        Args:
            frame: Current video frame
            tracked_object: The lost TrackedObject
            
        Returns:
            (success, bbox)
        """
        if tracked_object.template is None:
            return False, None
            
        try:
            template = tracked_object.template
            h_templ, w_templ = template.shape[:2]
            h_frame, w_frame = frame.shape[:2]
            
            if h_templ > h_frame or w_templ > w_frame:
                return False, None
                
            # Template Matching
            res = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            
            # Threshold > 0.7 as requested
            if max_val > 0.7:
                top_left = max_loc
                bottom_right = (top_left[0] + w_templ, top_left[1] + h_templ)
                
                bbox = (top_left[0], top_left[1], w_templ, h_templ)
                print(f"✅ Local recovery successful for #{tracked_object.id} (Conf: {max_val:.2f})")
                return True, bbox
            else:
                return False, None
                
        except Exception as e:
            print(f"❌ Error in local recovery: {e}")
            return False, None
