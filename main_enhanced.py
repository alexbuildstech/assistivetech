"""
Assistive Navigation System
Enhanced main application with voice control, multi-object tracking,
intelligent mode switching, and scene understanding.
"""

import cv2
import numpy as np
import time
import config
from vision_module import VisionController
from audio_module_multi import MultiAudioController
from voice_control import VoiceController
from mode_controller import ModeController
import json
import re
import os
from audio_coordinator import AudioCoordinator

def draw_enhanced_overlay(frame, mode_controller, tracking_status):
    """
    Draw comprehensive debug overlay with multi-object visualization.
    
    Args:
        frame: Video frame
        mode_controller: ModeController instance
        tracking_status: "TRACKING", "LOST", or "SEARCHING"
    """
    height, width = frame.shape[:2]
    
    # === TOP STATUS BAR ===
    status_height = 120
    status_bar = np.zeros((status_height, width, 3), dtype=np.uint8)
    status_bar[:] = config.COLOR_OVERLAY_BG
    
    # Status indicator with better messaging
    if tracking_status == "TRACKING":
        status_color = config.COLOR_TRACKING
        status_label = "[OK] Tracking"
    elif tracking_status == "SEARCHING":
        status_color = config.COLOR_SEARCHING
        status_label = "[SEARCH] Searching"
    else:
        status_color = config.COLOR_LOST
        status_label = "[READY] Ready"
    
    cv2.putText(status_bar, f"Status: {status_label}", (20, 30),
                config.FONT, 0.8, status_color, 2)
    
    # Mode info
    mode_desc = mode_controller.get_mode_description()
    cv2.putText(status_bar, f"Mode: {mode_desc}", (20, 60),
                config.FONT, 0.6, config.COLOR_TEXT, 1)
    
    # Object count
    obj_count = len(mode_controller.object_manager.objects)
    cv2.putText(status_bar, f"Objects: {obj_count}", (20, 90),
                config.FONT, 0.6, config.COLOR_TEXT, 1)
    
    # Controls hint
    cv2.putText(status_bar, "C:Record | S:Stop | D:Describe | M:Mode | Q:Quit", (width - 620, 30),
                config.FONT, 0.5, (200, 200, 200), 1)
    
    # Apply status bar
    frame[0:status_height, :] = status_bar
    
    # === DRAW OBJECT BOUNDING BOXES ===
    for obj in mode_controller.object_manager.objects:
        if obj.bbox:
            x, y, w, h = map(int, obj.bbox)
            
            # Determine color based on proximity zone
            zone = mode_controller.object_manager.get_proximity_zone(obj, width, height)
            zone_color = config.PROXIMITY_ZONES[zone]["color"]
            
            # Draw bounding box
            cv2.rectangle(frame, (x, y), (x + w, y + h), obj.color, 3)
            
            # Draw label
            label_text = f"#{obj.id} {obj.label}"
            cv2.putText(frame, label_text, (x, y - 10),
                        config.FONT, 0.6, obj.color, 2)
            
            # Draw proximity indicator
            cv2.circle(frame, (x + w - 20, y + 20), 10, zone_color, -1)
            
            # Draw predicted position if available
            if obj.predicted_bbox and config.MOTION_PREDICTION_ENABLED:
                px, py, pw, ph = map(int, obj.predicted_bbox)
                cv2.rectangle(frame, (px, py), (px + pw, py + ph), obj.color, 1, cv2.LINE_4)
                cv2.line(frame, (x + w//2, y + h//2), (px + pw//2, py + ph//2),
                        obj.color, 2, cv2.LINE_AA)
    
    # === RADAR DISPLAY ===
    radar_size = 150
    radar_x = width - radar_size - 20
    radar_y = height - radar_size - 20
    radar_center = (radar_x + radar_size // 2, radar_y + radar_size // 2)
    radar_radius = radar_size // 2 - 10
    
    # Draw radar background
    cv2.circle(frame, radar_center, radar_radius, config.COLOR_OVERLAY_BG, -1)
    cv2.circle(frame, radar_center, radar_radius, config.COLOR_TEXT, 2)
    
    # Draw crosshairs
    cv2.line(frame, (radar_center[0] - radar_radius, radar_center[1]),
             (radar_center[0] + radar_radius, radar_center[1]), config.COLOR_TEXT, 1)
    cv2.line(frame, (radar_center[0], radar_center[1] - radar_radius),
             (radar_center[0], radar_center[1] + radar_radius), config.COLOR_TEXT, 1)
    
    # Plot objects on radar
    for obj in mode_controller.object_manager.objects:
        if obj.bbox:
            # Calculate azimuth and elevation from bbox
            box_center_x = obj.bbox[0] + obj.bbox[2] / 2
            normalized_x = (box_center_x / width) * 2 - 1
            azimuth = normalized_x * config.MAX_AZIMUTH_DEGREES
            
            box_center_y = obj.bbox[1] + obj.bbox[3] / 2
            normalized_y = 1 - (box_center_y / height) * 2
            elevation = normalized_y * config.MAX_ELEVATION_DEGREES
            
            # Map to radar
            azimuth_norm = np.clip(azimuth / config.MAX_AZIMUTH_DEGREES, -1, 1)
            elevation_norm = np.clip(elevation / config.MAX_ELEVATION_DEGREES, -1, 1)
            
            indicator_x = int(radar_center[0] + azimuth_norm * radar_radius * 0.8)
            indicator_y = int(radar_center[1] - elevation_norm * radar_radius * 0.8)
            
            # Draw indicator
            indicator_radius = 6
            cv2.circle(frame, (indicator_x, indicator_y), indicator_radius, obj.color, -1)
            cv2.circle(frame, (indicator_x, indicator_y), indicator_radius + 1, config.COLOR_TEXT, 1)
    
    # Radar label
    cv2.putText(frame, "RADAR", (radar_x + 45, radar_y - 10),
                config.FONT, 0.5, config.COLOR_TEXT, 1)
    
    return frame


class NonBlockingConsole:
    """
    Enables non-blocking terminal input for controlling the app without window focus.
    Works on Linux/Unix.
    """
    def __init__(self):
        import sys
        import select
        import tty
        import termios
        self.sys = sys
        self.select = select
        self.tty = tty
        self.termios = termios
        self.old_settings = termios.tcgetattr(sys.stdin)
        self.enabled = False

    def __enter__(self):
        try:
            self.tty.setcbreak(self.sys.stdin.fileno())
            self.enabled = True
        except Exception:
            pass # Likely not a TTY
        return self

    def __exit__(self, type, value, traceback):
        if self.enabled:
            self.termios.tcsetattr(self.sys.stdin, self.termios.TCSADRAIN, self.old_settings)

    def get_key(self):
        """Return a key if available, else None."""
        if not self.enabled:
            return None
        
        if self.select.select([self.sys.stdin], [], [], 0)[0]:
            try:
                return self.sys.stdin.read(1)
            except IOError:
                return None
        return None


def main():
    """Enhanced main application entry point."""
    vision_controller = None
    audio_controller = None
    audio_coordinator = None
    voice_controller = None
    mode_controller = None
    
    # Initialize Console Input
    console = NonBlockingConsole()
    
    try:
        print("=" * 70)
        print("NOVA ASSISTIVE NAVIGATION")
        print("=" * 70)
        print("Features: Voice Control | Multi-Object | Intelligent Modes | Scene AI")
        print("=" * 70)
        print()
        
        # Enter non-blocking mode
        with console:
            # === Initialization ===
            print("[1/7] Initializing Vision Controller...")
            vision_controller = VisionController()
            
            # [2/7] Initializing Audio Controller
            print("\n[2/7] Initializing Audio Controller...")
            audio_controller = None
            if config.ENABLE_HRTF:
                try:
                    from audio_hrtf import HRTF_AudioController
                    audio_controller = HRTF_AudioController()
                    # Check if it actually initialized (not dummy)
                    if hasattr(audio_controller, 'is_dummy') and audio_controller.is_dummy:
                        print("⚠️ HRTF reported as dummy. Falling back to MultiAudio.")
                        audio_controller = None
                except Exception as e:
                    print(f"⚠️ Could not initialize HRTF Audio: {e}. Falling back...")
                    audio_controller = None
                    
            if audio_controller is None:
                from audio_module_multi import MultiAudioController
                audio_controller = MultiAudioController()
            
            print("[3/7] Initializing Voice Controller...")
            try:
                voice_controller = VoiceController()
                voice_enabled = True
            except Exception as e:
                print(f"⚠️ Voice control unavailable: {e}")
                print("   Continuing without voice features...")
                voice_enabled = False
            
            print("\n[4/7] Initializing Mode Controller...")
            mode_controller = ModeController()
            mode_controller.set_frame_dimensions(
                vision_controller.frame_width,
                vision_controller.frame_height
            )
            
            # === Initialize Learning Module ===
            learning_module = None
            if config.ENABLE_LEARNING:
                print("\n[5/7] Initializing Self-Learning System...")
                from learning_module import LearningModule
                learning_module = LearningModule()
                stats = learning_module.get_stats()
                print(f"   [LEARNING] Learned: {stats['total_detections']} detections, {stats['unique_labels']} object types")
                print(f"   [LEARNING] Cache: {stats['cached_images']} images ({stats['cache_size_mb']:.1f} MB)")
            
            # === Initialize Hardware Interface ===
            print("\n[6/7] Initializing Hardware Interface (Arduino)...")
            hardware_interface = None
            try:
                from hardware_interface import HardwareInterface, DummyHardwareInterface
                if config.ENABLE_HARDWARE:
                    hardware_interface = HardwareInterface()
                    if not hardware_interface.is_connected:
                        print("⚠️ Hardware connection failed. Using dummy interface.")
                        hardware_interface = DummyHardwareInterface()
                else:
                    hardware_interface = DummyHardwareInterface()
            except Exception as e:
                print(f"⚠️ Hardware init failed: {e}")
                from hardware_interface import DummyHardwareInterface
                hardware_interface = DummyHardwareInterface()

            # === Initialize Shared State ===
            print("\n[7/7] Initializing Shared State & Audio...")
            import threading
            from shared_state import SharedGameState
            shared_state = SharedGameState()
            
            # Start Audio Thread with shared_state
            audio_controller.start_stream(shared_state)
            
            # Initialize and start AudioCoordinator for spatial audio
            audio_coordinator = AudioCoordinator(audio_controller, shared_state)
            audio_coordinator.start()
            
            # Voice listener removed - C/S keys handled directly in main loop
            
            print("\n" + "=" * 70)
            print("SYSTEM READY")
            print("=" * 70)
            print("Controls (Window OR Terminal):")
            print("   C - Start recording (voice)")
            print("   S - Stop and transcribe (voice)")
            print("   D - Describe scene")
            print("   F - Find objects (manual detection)" if config.MANUAL_MODE else "")
            print("   M - Cycle modes")
            print("   N - Normal Mode (Reset)")
            print("   R - Re-acquire")
            print("   Q - Quit")
            if config.MANUAL_MODE:
                print(f"\n[MODE] MANUAL MODE: Press 'F' to trigger detection")
            if voice_enabled:
                print(f"\n[VOICE] Voice Commands:")
                print("   'Track [object]' - Track specific object")
                print("   'Find [object]' - Manual detection")
                print("   'Describe scene' - Get AI narration")
                print("   '[Mode] mode' - Switch modes")
                print("   'Stop tracking' - Clear all objects")
            print("=" * 70 + "\n")
        
            # Vision Thread Function
            def vision_worker():
                print("[VISION] Vision thread started")
                
                while shared_state.is_running:
                    # 1. Get latest frame
                    frame = shared_state.get_latest_frame()
                    if frame is None:
                        time.sleep(0.01)
                        continue
                        
                    # 2. Check for Async Detection Results (Non-blocking)
                    detections = vision_controller.check_reacquisition_result()
                    if detections is not None:
                        print(f"[VISION] Async detection complete. Processing {len(detections)} objects...")
                        
                        # Process results on CURRENT frame
                        # Note: Detections are from the past (approx 1-2s ago), but we merge them
                        # intelligently. If tracker has kept up, we won't overwrite it with old data.
                        count = mode_controller.process_detections(detections, frame)
                        
                        if count > 0:
                            # Apply mode-specific filtering (e.g., SOCIAL mode only tracks people)
                            if mode_controller.should_filter_objects():
                                filter_labels = mode_controller.get_object_filter()
                                mode_controller.object_manager.filter_by_labels(filter_labels)
                                print(f"   [VISION] Filtered to {filter_labels} only")
                            
                            # Apply max objects limit from mode config
                            max_objects = mode_controller.get_max_objects()
                            mode_controller.object_manager.limit_objects(max_objects)
                            
                            # Initialize trackers for NEW objects only
                            mode_controller.object_manager.init_all_trackers(frame)
                            
                            # Save to learning database
                            if learning_module:
                                for obj in mode_controller.object_manager.objects:
                                    if obj.bbox:
                                        learning_module.save_detection(
                                            frame, obj.label, obj.bbox, obj.confidence,
                                            vision_controller.frame_width,
                                            vision_controller.frame_height,
                                            context=obj.context
                                        )
                            
                            # We can't easily check if this was a "manual" detect command here since it's async
                            # But we can check if we should speak based on recent commands or state
                            if voice_enabled: 
                                voice_controller.speak(f"Found {count} objects", async_mode=True)

                    # 3. Handle "detect" command (Start Async)
                    command = shared_state.get_next_command()
                    should_detect = (command == "detect")
                    
                    if should_detect:
                        if not vision_controller.is_searching:
                            print("\n[VISION] Vision Thread: Starting ASYNC detection...")
                            
                            # OPTIMIZATION: Resize for faster upload/processing
                            if frame is None or frame.size == 0:
                                print("[WARNING] Empty frame, skipping detection")
                                continue
                                
                            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
                            
                            # Start Async Detection
                            prompt = mode_controller.get_detection_prompt()
                            vision_controller.start_reacquisition_multi(small_frame, prompt)
                        else:
                            print("[WARNING] Detection already in progress, skipping request.")
                    
                    
                    # 4. Run Trackers (OpenCV) - High Frequency
                    # Only track if we have objects
                    if mode_controller.object_manager.objects:
                        # Update trackers
                        mode_controller.object_manager.update_trackers(frame)
                        
                        # Update shared state so audio thread can generate sounds
                        objects = mode_controller.object_manager.objects
                        status = "TRACKING" if objects else "READY"
                        shared_state.update_tracking(objects, status)
                    else:
                        shared_state.update_tracking([], "READY")
                    
                    # 4. Check for Lost Threats (Fallback Logic)
                    # Attempt Local Recovery First
                    for obj in mode_controller.object_manager.objects:
                        if obj.is_lost and obj.template is not None:
                            # Try local recovery
                            success, new_bbox = vision_controller.attempt_local_recovery(frame, obj)
                            if success:
                                # Re-initialize tracker
                                obj.bbox = new_bbox
                                mode_controller.object_manager.init_tracker(obj.id, frame)
                                obj.is_lost = False
                                obj.lost_time = None
                                # Update template with new view
                                mode_controller.object_manager.update_template(obj, frame)
                                
                        # Update template if tracking is good (every 1s roughly)
                        elif not obj.is_lost and obj.tracker:
                            if time.time() - obj.last_template_update > 1.0:
                                mode_controller.object_manager.update_template(obj, frame)

                    # Check for stale trackers (30s timeout)
                    if mode_controller.object_manager.cleanup_stale_trackers(max_age=30.0):
                        print("[VISION] Stale trackers removed. Triggering re-scan.")
                        shared_state.add_command("detect")

                    if mode_controller.check_lost_threats():
                        print("[WARNING] Critical threat lost! Forcing re-scan...")
                        shared_state.add_command("detect")
                        if voice_enabled:
                            voice_controller.speak("Lost track. Rescanning.", async_mode=True)
                        
                    # === VISION UPDATE FREQUENCY ===
                    # Vision runs slower than UI to save CPU
                    time.sleep(0.05) # 20 FPS for vision processing
                
                print("[VISION] Vision thread stopped")
        
            # Start vision thread
            vision_thread = threading.Thread(target=vision_worker, daemon=True)
            vision_thread.start()
            
            print("\n[SYSTEM] System is live! Press 'Q' to quit.")
            
            # === Main Application Loop (Video/UI Only) ===
            try:
                # Initialize frame capture variable at loop scope
                captured_frame_for_qa = None
                
                # Performance: Pre-allocate display frame buffer
                display_frame_buffer = None
                last_frame_shape = None
                
                # FPS tracking
                fps_frame_count = 0
                fps_start_time = time.time()
                current_fps = 0.0
                
                # Error tracking
                consecutive_frame_failures = 0
                max_frame_failures = 10
                
                while True:
                    if not shared_state.is_running:
                        break
                    
                    loop_start = time.time()
                    
                    # 1. Read current frame
                    ret, frame = vision_controller.read_frame()
                    if not ret or frame is None:
                        consecutive_frame_failures += 1
                        if consecutive_frame_failures >= max_frame_failures:
                            print(f"[ERROR] Failed to read frame {max_frame_failures} times. Exiting.")
                            break
                        time.sleep(0.01)
                        continue
                    
                    # Success - reset counter
                    consecutive_frame_failures = 0
                    
                    # === OPTIMIZED ROTATION LOGIC ===
                    h, w = frame.shape[:2]
                    # Process only right half + rotate + resize in one go
                    right_half = frame[:, w // 2:]
                    rotated = cv2.rotate(right_half, cv2.ROTATE_90_CLOCKWISE)
                    frame = cv2.resize(rotated, (config.CAMERA_WIDTH, config.CAMERA_HEIGHT))
                    
                    # Update dimensions only when needed (avoid repeated checks)
                    if config.CAMERA_WIDTH != mode_controller.frame_width:
                        mode_controller.set_frame_dimensions(config.CAMERA_WIDTH, config.CAMERA_HEIGHT)
                        vision_controller.frame_width = config.CAMERA_WIDTH
                        vision_controller.frame_height = config.CAMERA_HEIGHT
        
                    # 2. Update Shared State (zero-copy reference swap)
                    shared_state.update_frame(frame)
                    
                    # 3. Get tracking state efficiently
                    objects, status = shared_state.get_tracking_state()
                    
                    # 4. Draw Overlay - optimized path
                    mode_controller.object_manager.objects = objects
                    
                    # Reuse display buffer if shape matches (avoid reallocation)
                    if display_frame_buffer is None or frame.shape != last_frame_shape:
                        display_frame_buffer = frame.copy()
                        last_frame_shape = frame.shape
                    else:
                        # Copy into existing buffer (faster than allocating new)
                        np.copyto(display_frame_buffer, frame)
                    
                    # Only draw overlay if we have objects or status changed
                    if objects or status != "READY":
                        display_frame_buffer = draw_enhanced_overlay(
                            display_frame_buffer, mode_controller, status
                        )
                    
                    # 5. Display Frame
                    cv2.imshow("Nova Assistive Glasses", display_frame_buffer)
                    
                    # Calculate and update FPS
                    fps_frame_count += 1
                    elapsed = time.time() - fps_start_time
                    if elapsed >= 1.0:
                        current_fps = fps_frame_count / elapsed
                        shared_state.set_fps(current_fps)
                        fps_frame_count = 0
                        fps_start_time = time.time()
                    
                    # 6. Handle Input (Window OR Terminal)
                    key = cv2.waitKey(1) & 0xFF
                    
                    # Also check terminal input specifically
                    term_key = console.get_key()
                    if term_key:
                        key = ord(term_key.lower())
                    
                    if key == ord('q') or key == ord('Q'):
                        break
                    
                    # Check Hardware Inputs (Standalone - doesn't block key handling)
                    if hardware_interface:
                        pressure = hardware_interface.get_pressure()
                        if pressure > config.PRESSURE_THRESHOLD:
                             print(f"************ SQUEEZE DETECTED ({pressure}) ************")
                             # Potential action: Trigger Stop or Record?
                             # For now just log it to prove it works.
                    
                    # Key handlers (separate from hardware check)
                    if key == ord('f') or key == ord('F'):
                        print("⚡ Triggering detection...")
                        shared_state.add_command("detect")
                    elif key == ord('c') or key == ord('C'):
                        if voice_enabled:
                            # 1. Stop any ongoing TTS/Audio immediately (Prevent Segfault)
                            voice_controller.stop_speaking()
                            
                            # 2. INSTANT CAPTURE: Grab frame immediately when button is pressed
                            # This ensures we see exactly what the user is pointing at
                            frame_for_capture = shared_state.peek_frame()
                            if frame_for_capture is not None:
                                captured_frame_for_qa = frame_for_capture.copy()
                                print("[VISION] Frame captured immediately for query")
                            else:
                                captured_frame_for_qa = None
                                print("[WARNING] No frame available for capture")

                            # 3. Stop Tracking (Clear "F Mode")
                            mode_controller.object_manager.clear()
                            shared_state.update_tracking([], "READY")

                            # 4. Start Recording
                            print("\n[VOICE] Recording started (press 'S' to stop)")
                            voice_controller.start_recording()
                        else:
                            print("[ERROR] Voice control not enabled")
                    elif key == ord('s') or key == ord('S'):
                        if voice_enabled and voice_controller.is_recording:
                            # Run voice processing in a separate thread to avoid blocking UI
                            # Capture context variables
                            current_qa_frame = captured_frame_for_qa if 'captured_frame_for_qa' in locals() else None
                            current_frame = frame.copy()
                            
                            def process_voice_thread(qa_frame, live_frame):
                                # Stop recording and get transcription
                                text = voice_controller.stop_recording()
                                
                                # Resume HRTF audio
                                if audio_controller:
                                    audio_controller.resume_stream()
                                    
                                if text:
                                    print(f"[VOICE] Voice: {text}")
                                    # Handle voice commands
                                    command = voice_controller.parse_command(text)
                                    if command:
                                        intent = command["intent"]
                                        params = command.get("params", {})
                                        
                                        if intent == "track_object":
                                            obj_name = params.get("object", "phone")
                                            mode_controller.set_target_object(obj_name)
                                            mode_controller.set_mode(config.NavigationMode.NAVIGATION)
                                            voice_controller.speak(f"Tracking {obj_name}", async_mode=True)
                                            shared_state.add_command("detect")
                                        
                                        elif intent.startswith("mode_"):
                                            mode_name = intent.replace("mode_", "")
                                            if mode_controller.set_mode(mode_name):
                                                voice_controller.speak(f"{mode_name} mode activated", async_mode=True)
                                                shared_state.add_command("detect")
                                        
                                        elif intent == "describe_scene":
                                            print("[VISION] Describing scene...")
                                            vision_controller.describe_scene(live_frame, voice_controller)
                                        
                                        elif intent == "visual_qa":
                                            question = params.get("question", "What is this?")
                                            print(f"[VISION] Asking AI: {question}")
                                            
                                            # Use the frame captured at the START of recording (Instant Capture)
                                            target_frame = qa_frame if qa_frame is not None else live_frame
                                            
                                            # Pass history for context
                                            history = voice_controller.conversation_manager.get_context_string()
                                            vision_controller.ask_about_scene(target_frame, question, voice_controller, history)
                                        
                                        elif intent == "recall_object":
                                            obj_name = params.get("object", "object")
                                            if learning_module:
                                                print(f"[LEARNING] Recalling: {obj_name}...")
                                                recall_info = learning_module.recall_object(obj_name)
                                                if recall_info:
                                                    response = f"{obj_name.capitalize()} was last seen {recall_info['location_desc']}, {recall_info['time_ago']}"
                                                    print(f"  [OK] {response}")
                                                    voice_controller.speak(response, async_mode=False)
                                                else:
                                                    response = f"I haven't seen {obj_name} yet"
                                                    print(f"  [NOT FOUND] {response}")
                                                    voice_controller.speak(response, async_mode=True)
                                            else:
                                                voice_controller.speak("Learning system not enabled", async_mode=True)
                                        
                                        elif intent == "direct_response":
                                            response = params.get("response", "")
                                            print(f"[AI] Nova: {response}")
                                            voice_controller.speak(response, async_mode=True)

                                        elif intent == "chat_with_nova":
                                            text = params.get("text", "")
                                            voice_controller.chat_with_nova(text)
                                        
                                        elif intent == "stop_tracking":
                                            mode_controller.object_manager.clear()
                                            voice_controller.speak("Tracking stopped", async_mode=True)
                                            shared_state.update_tracking([], "READY")
                                        
                                        elif intent == "help":
                                            voice_controller.speak(voice_controller.get_help_text(), async_mode=False)
                                        
                                        elif intent == "quit":
                                            voice_controller.speak("Goodbye", async_mode=True)
                                            time.sleep(1)
                                            shared_state.is_running = False
                                        
                                        elif intent == "unknown":
                                            voice_controller.speak("Sorry, I didn't understand that command", async_mode=True)
                            
                            # Start thread
                            threading.Thread(target=process_voice_thread, 
                                           args=(current_qa_frame, current_frame), 
                                           daemon=True).start()
                    
                    elif key == ord('d') or key == ord('D'):
                        print("\n[VISION] Describing scene...")
                        if voice_enabled:
                            vision_controller.describe_scene(frame, voice_controller)
                        else:
                            description = vision_controller.get_scene_description(frame)
                            print(f"Scene: {description}")
                    
                    elif key == ord('m') or key == ord('M'):
                        # Hardened mode cycling
                        available_modes = [
                            config.NavigationMode.NAVIGATION, 
                            config.NavigationMode.OBSTACLE,
                            config.NavigationMode.SOCIAL, 
                            config.NavigationMode.EXPLORATION
                        ]
                        try:
                            current_idx = available_modes.index(mode_controller.current_mode)
                        except ValueError:
                            current_idx = -1 # Start from beginning
                            
                        next_mode = available_modes[(current_idx + 1) % len(available_modes)]
                        mode_controller.set_mode(next_mode)
                        if voice_enabled:
                            voice_controller.speak(f"{next_mode} mode", async_mode=True)
                        shared_state.add_command("detect")
                    
                    elif key == ord('n') or key == ord('N'):
                        print("\n[SYSTEM] System Reset: Normal Mode")
                        mode_controller.set_mode(config.NavigationMode.EXPLORATION)
                        mode_controller.object_manager.clear()
                        # Ensure voice controller is ready (stop any recording)
                        if voice_enabled and voice_controller.is_recording:
                            voice_controller.stop_recording()
                        if voice_enabled:
                            voice_controller.speak("Normal mode", async_mode=True)
                        shared_state.add_command("detect")
                    
                    elif key == ord('r') or key == ord('R'):
                        print("\n[SYSTEM] Manual re-acquisition...")
                        mode_controller.object_manager.clear()
                        shared_state.add_command("detect")
                        
                    # Wait for 1ms to allow UI updates
                    # time.sleep(0.001) # Not needed with waitKey(1)

            except KeyboardInterrupt:
                print("\n[SYSTEM] Interrupted by user")
            finally:
                shared_state.is_running = False # Signal threads to stop
                vision_thread.join(timeout=5) # Wait for vision thread to finish
                if audio_coordinator:
                    audio_coordinator.stop()
                audio_controller.stop_stream()
                vision_controller.release()
                cv2.destroyAllWindows()

    
    except KeyboardInterrupt:
        print("\n\n[SYSTEM] Program interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Critical error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
