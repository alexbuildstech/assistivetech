"""
Audio Coordinator Module - Bridges vision tracking and spatial audio output.
Ensures audio signatures are actually generated based on tracked objects.
"""

import threading
import time
import config

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False


class AudioCoordinator:
    """
    Coordinates between tracked objects and spatial audio output.
    Runs in background thread to continuously update audio based on object positions.
    """

    def __init__(self, audio_controller, shared_state):
        """
        Initialize audio coordinator.

        Args:
            audio_controller: MultiAudioController or HRTF_AudioController instance
            shared_state: SharedGameState instance
        """
        self.audio_controller = audio_controller
        self.shared_state = shared_state
        self.running = False
        self.coordinator_thread = None

        # Track which objects are currently audible
        self.active_audio_objects = set()

        print("🎧 AudioCoordinator initialized")

    def start(self):
        """Start the audio coordination thread."""
        if self.running:
            return

        self.running = True
        self.coordinator_thread = threading.Thread(
            target=self._coordination_loop, daemon=True
        )
        self.coordinator_thread.start()
        print("▶️ Audio coordination started")

    def stop(self):
        """Stop the audio coordination thread."""
        self.running = False
        if self.coordinator_thread:
            self.coordinator_thread.join(timeout=1.0)
        print("⏹️ Audio coordination stopped")

    def _coordination_loop(self):
        """
        Main coordination loop - updates audio sources based on tracked objects.
        Runs at ~20Hz to match vision updates.
        """
        while self.running and self.shared_state.is_running:
            try:
                objects, status = self.shared_state.get_tracking_state()

                if objects and status == "TRACKING":
                    self._update_audio_sources(objects)
                else:
                    # No objects or not tracking - clear audio
                    if self.active_audio_objects:
                        self.audio_controller.clear_sources()
                        self.active_audio_objects.clear()

                # Update at 20Hz (50ms)
                time.sleep(0.05)

            except Exception as e:
                print(f"⚠️ Audio coordination error: {e}")
                time.sleep(0.1)

    def _update_audio_sources(self, objects):
        """
        Update audio sources based on current object positions.

        Args:
            objects: List of TrackedObject instances
        """
        current_ids = set()

        for obj in objects:
            if not obj.bbox:
                continue

            obj_id = obj.id
            current_ids.add(obj_id)

            # Calculate spatial audio parameters from bounding box
            frame_width = config.CAMERA_WIDTH
            frame_height = config.CAMERA_HEIGHT

            center_x = obj.bbox[0] + obj.bbox[2] / 2
            center_y = obj.bbox[1] + obj.bbox[3] / 2

            # Calculate azimuth (horizontal angle) - normalized to -80 to +80 degrees
            # Center of frame = 0 degrees (straight ahead)
            # Left side = negative, Right side = positive
            normalized_x = (center_x / frame_width) * 2 - 1  # -1 to 1
            azimuth = normalized_x * config.MAX_AZIMUTH_DEGREES

            # Calculate volume based on proximity (object size)
            # Larger objects (closer) = louder
            obj_area = obj.bbox[2] * obj.bbox[3]
            frame_area = frame_width * frame_height
            size_ratio = obj_area / frame_area

            # Map size ratio to volume (0.1 to 1.0)
            # Closer/larger objects get higher volume
            volume = min(
                1.0, max(0.1, size_ratio * 3)
            )  # Multiply by 3 to boost smaller objects

            # Boost volume for high-threat objects
            if hasattr(obj, "threat_score") and obj.threat_score > 0.5:
                volume = min(1.0, volume * 1.3)  # 30% volume boost for threats

            # Determine audio signature based on object label
            signature_name = self._get_signature_name(obj.label)

            # Update or create audio source
            if obj_id not in self.active_audio_objects:
                # New object - add to tracking
                self.active_audio_objects.add(obj_id)
                print(
                    f"  🎵 Audio source added: {obj.label} (ID: {obj_id}) - {signature_name} sound"
                )

            # Update the audio source position and volume
            self.audio_controller.update_source(obj_id, azimuth, volume, signature_name)

        # Remove audio sources for objects no longer tracked
        stale_ids = self.active_audio_objects - current_ids
        for obj_id in stale_ids:
            self.audio_controller.remove_source(obj_id)
            self.active_audio_objects.discard(obj_id)
            print(f"  🔇 Audio source removed: ID {obj_id}")

    def _get_signature_name(self, label):
        """
        Map object label to audio signature name.

        Args:
            label: Object label string (e.g., "Phone", "Red Cup", "Person")

        Returns:
            Signature name for audio generation
        """
        # Normalize label
        label_lower = label.lower()

        # Map to signature names defined in config.AUDIO_SIGNATURES
        if "person" in label_lower or "human" in label_lower:
            return "person"
        elif "hand" in label_lower:
            return "person"  # Use person signature (heartbeat) for hands
        elif "phone" in label_lower or "mobile" in label_lower:
            return "phone"
        elif "door" in label_lower:
            return "door"
        elif "chair" in label_lower:
            return "chair"
        elif "table" in label_lower:
            return "table"
        elif "cup" in label_lower or "mug" in label_lower:
            return "cup"
        elif (
            "obstacle" in label_lower
            or "wall" in label_lower
            or "furniture" in label_lower
        ):
            return "obstacle"
        else:
            return "default"
