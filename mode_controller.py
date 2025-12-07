"""
Mode Controller Module for Intelligent Navigation Mode Switching.
Manages different operating modes with context-aware behavior.
"""

import cv2
import numpy as np
import time
import config
from object_manager import ObjectManager

class ModeController:
    """
    Manages navigation modes and coordinates system behavior.
    """
    
    def __init__(self):
        """Initialize mode controller."""
        self.current_mode = config.DEFAULT_MODE
        self.target_object = "phone"  # Default tracking target
        self.object_manager = ObjectManager()
        
        print(f"🎮 ModeController initialized | Mode: {self.current_mode}")
    
    def set_mode(self, mode):
        """
        Switch to a new mode.
        
        Args:
            mode: Mode name from config.NavigationMode
        
        Returns:
            True if mode changed, False if invalid mode
        """
        if mode not in config.MODE_CONFIGS:
            print(f"❌ Invalid mode: {mode}")
            return False
        
        if mode == self.current_mode:
            print(f"ℹ️ Already in {mode} mode")
            return True
        
        old_mode = self.current_mode
        self.current_mode = mode
        
        # Clear objects when switching modes
        self.object_manager.clear()
        
        mode_desc = config.MODE_CONFIGS[mode]["description"]
        print(f"🔄 Mode changed: {old_mode} → {self.current_mode} ({mode_desc})")
        
        return True
    
    def get_mode_config(self):
        """Get configuration for current mode."""
        return config.MODE_CONFIGS.get(self.current_mode, {})
    
    def get_detection_prompt(self):
        """
        Get the appropriate detection prompt for current mode.
        
        Returns:
            Formatted prompt string
        """
        mode_config = self.get_mode_config()
        prompt_template = mode_config.get("prompt", config.DETECTION_PROMPT_MULTI_OBJECT)
        
        # Format with target object if needed
        if "{target_object}" in prompt_template:
            return prompt_template.format(target_object=self.target_object)
        
        return prompt_template
    
    def set_target_object(self, obj_name):
        """
        Set the target object to track (for navigation mode).
        
        Args:
            obj_name: Object name (e.g., "phone", "person", "door")
        """
        self.target_object = obj_name
        print(f"🎯 Target object set to: {obj_name}")
        
        # If in navigation mode, clear current objects to force new detection
        if self.current_mode == config.NavigationMode.NAVIGATION:
            self.object_manager.clear()
    
    def should_filter_objects(self):
        """Check if current mode requires object filtering."""
        mode_config = self.get_mode_config()
        return "filter" in mode_config
    
    def get_object_filter(self):
        """Get the label filter for current mode."""
        mode_config = self.get_mode_config()
        return mode_config.get("filter", [])
    
    def get_max_objects(self):
        """Get maximum number of objects for current mode."""
        mode_config = self.get_mode_config()
        return mode_config.get("max_objects", config.MAX_TRACKED_OBJECTS)
    
    def get_audio_focus_strategy(self):
        """
        Get the audio focus strategy for current mode.
        
        Returns:
            Strategy name: "target", "closest", "people", "all"
        """
        mode_config = self.get_mode_config()
        return mode_config.get("audio_focus", "all")
    
    def process_detections(self, detections, frame):
        """
        Process Gemini detection results into tracked objects.
        
        Args:
            detections: List of detection dicts from Gemini
            frame: Current video frame (for dimensions)
        
        Returns:
            Number of objects added
        """
        if not detections:
            return 0
        
        # SIMPLIFIED: Clear all existing objects and add fresh detections
        # This removes the buggy retracking logic that caused stale bounding boxes
        # self.object_manager.clear() # REMOVED for persistence
        
        count = 0
        frame_height, frame_width = frame.shape[:2]
        import time
        
        for det in detections:
            try:
                # Extract normalized coordinates (0-1000 range)
                box_2d = det.get("box_2d", [])
                label = det.get("label", "unknown")
                
                if len(box_2d) != 4:
                    continue
                
                # Convert from normalized (0-1000) to pixel coordinates
                y_min, x_min, y_max, x_max = box_2d
                x = int(x_min * frame_width / 1000)
                y = int(y_min * frame_height / 1000)
                w = int((x_max - x_min) * frame_width / 1000)
                h = int((y_max - y_min) * frame_height / 1000)
                
                # Validate and clamp bounding box
                x = max(0, min(x, frame_width - 1))
                y = max(0, min(y, frame_height - 1))
                w = max(1, min(w, frame_width - x))
                h = max(1, min(h, frame_height - y))
                
                if w < 5 or h < 5:
                    continue
                
                new_bbox = (x, y, w, h)
                
                # Parse label for context (e.g. "Phone [on table]")
                import re
                context = None
                match = re.search(r"^(.*?)\[(.*?)\]", label)
                if match:
                    label = match.group(1).strip()
                    context = match.group(2).strip()
                
                # Try to match with existing object
                matched = False
                for existing_obj in self.object_manager.objects:
                    # Check label match (fuzzy or exact)
                    if existing_obj.label == label: 
                        iou = self.object_manager.compute_iou(existing_obj.bbox, new_bbox)
                        
                        # SMART MERGING:
                        # If object is currently tracked (not lost), be very conservative about updating 
                        # its position from detection, because detection might be stale (laggy).
                        # Only update if:
                        # 1. Object is LOST (we need to find it)
                        # 2. IoU is very high (it hasn't moved much)
                        
                        should_update_bbox = False
                        
                        if existing_obj.is_lost:
                            # If lost, accept the new detection if it matches reasonably well
                            if iou > 0.1: # Loose threshold for recovery
                                should_update_bbox = True
                        else:
                            # If currently tracking, only update if it matches VERY well
                            # This prevents "jumping" back to old positions due to API latency
                            if iou > 0.6: 
                                should_update_bbox = True
                        
                        if should_update_bbox:
                            existing_obj.bbox = new_bbox
                            # print(f"🔄 Updated object #{existing_obj.id}: {label} (IoU={iou:.2f})")
                        
                        # ALWAYS update metadata
                        if iou > 0.1: # If it's likely the same object
                            existing_obj.last_verified = time.time()
                            existing_obj.context = context # Update context
                            existing_obj.is_lost = False
                            existing_obj.lost_time = None
                            matched = True
                            break
                
                if not matched:
                    # Add new object
                    obj = self.object_manager.add_object(label, new_bbox, context=context)
                    print(f"➕ Added object #{obj.id}: {label} at {new_bbox} (Context: {context})")
                    count += 1
                
            except Exception as e:
                print(f"❌ Error processing detection: {e}")
                continue
        
        return count


    def _convert_bbox(self, box_2d, frame_width=640, frame_height=480):
        """
        Convert normalized bounding box to pixel coordinates.
        
        Args:
            box_2d: [y_min, x_min, y_max, x_max] normalized 0-1000
            frame_width, frame_height: Frame dimensions
        
        Returns:
            (x, y, w, h) in pixels
        """
        if not box_2d or len(box_2d) != 4:
            return None
        
        y_min, x_min, y_max, x_max = box_2d
        
        x1 = int((x_min / 1000) * frame_width)
        y1 = int((y_min / 1000) * frame_height)
        x2 = int((x_max / 1000) * frame_width)
        y2 = int((y_max / 1000) * frame_height)
        
        return (x1, y1, x2 - x1, y2 - y1)
    
    def set_frame_dimensions(self, width, height):
        """Store frame dimensions for bbox conversion."""
        self.frame_width = width
        self.frame_height = height
    
    def get_primary_object(self):
        """
        Get the primary object to focus on based on current mode strategy.
        
        Returns:
            TrackedObject or None
        """
        strategy = self.get_audio_focus_strategy()
        
        if not self.object_manager.objects:
            return None
        
        if strategy == "target":
            # Find object matching target label
            targets = self.object_manager.get_objects_by_label(self.target_object)
            return targets[0] if targets else self.object_manager.objects[0]
        
        elif strategy == "closest":
            # Get closest object (largest bbox)
            return self.object_manager.get_closest_object(
                self.frame_width if hasattr(self, 'frame_width') else 640,
                self.frame_height if hasattr(self, 'frame_height') else 480
            )
        
        elif strategy == "people":
            # Get first person
            people = self.object_manager.get_objects_by_label("person")
            return people[0] if people else None
        
        elif strategy == "all":
            # Return all objects (caller should handle multiple)
            return self.object_manager.objects
        
        return None
    
    def get_mode_description(self):
        """Get human-readable description of current mode."""
        mode_config = self.get_mode_config()
        return mode_config.get("description", self.current_mode)

    def get_main_threat(self):
        """
        Get the object with the highest threat score.
        
        Returns:
            TrackedObject or None
        """
        if not self.object_manager.objects:
            return None
            
        # Sort by threat score descending
        sorted_objects = sorted(self.object_manager.objects, key=lambda o: o.threat_score, reverse=True)
        return sorted_objects[0]

    def check_lost_threats(self):
        """
        Check if the main threat has been lost for too long.
        
        Returns:
            True if a re-scan is needed, False otherwise.
        """
        main_threat = self.get_main_threat()
        if not main_threat:
            return False
            
        # If the main threat is lost
        if main_threat.is_lost and main_threat.lost_time:
            elapsed = time.time() - main_threat.lost_time
            
            # Only trigger if it's a significant threat (score > 0.3)
            if main_threat.threat_score > 0.3 and elapsed > 2.0:
                print(f"⚠️ Main threat '{main_threat.label}' (Score: {main_threat.threat_score:.2f}) lost for {elapsed:.1f}s. Triggering re-scan.")
                # Remove the stale object so we don't keep checking it
                self.object_manager.remove_object(main_threat.id)
                return True
        
        return False
