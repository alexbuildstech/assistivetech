"""
Object Manager Module for Multi-Object Tracking.
Handles detection, tracking, and management of multiple objects with unique identities.
"""

import cv2
import numpy as np
import config
from dataclasses import dataclass
from typing import List, Optional, Dict
import time

@dataclass
class TrackedObject:
    """Represents a single tracked object with all its properties."""
    
    id: int
    label: str
    bbox: tuple  # (x, y, w, h)
    tracker: Optional[cv2.Tracker]
    confidence: float
    audio_signature: Dict
    color: tuple  # BGR color for visualization
    last_update: float
    velocity: Optional[tuple] = None  # (vx, vy) pixels/frame
    predicted_bbox: Optional[tuple] = None
    threat_score: float = 0.0
    is_lost: bool = False
    lost_time: Optional[float] = None
    template: Optional[np.ndarray] = None
    last_template_update: float = 0.0
    context: Optional[str] = None
    last_verified: float = 0.0
    
    def update_velocity(self, new_bbox):
        """Calculate velocity based on bbox movement."""
        if self.bbox:
            old_center_x = self.bbox[0] + self.bbox[2] / 2
            old_center_y = self.bbox[1] + self.bbox[3] / 2
            new_center_x = new_bbox[0] + new_bbox[2] / 2
            new_center_y = new_bbox[1] + new_bbox[3] / 2
            
            vx = new_center_x - old_center_x
            vy = new_center_y - old_center_y
            
            self.velocity = (vx, vy)
        
        self.bbox = new_bbox
        self.last_update = time.time()
    
    def predict_position(self, horizon_seconds=0.5):
        """Predict future position based on current velocity."""
        if not self.velocity or not self.bbox:
            self.predicted_bbox = self.bbox
            return
        
        vx, vy = self.velocity
        
        # Only predict if actually moving
        if abs(vx) < config.MIN_VELOCITY_THRESHOLD and abs(vy) < config.MIN_VELOCITY_THRESHOLD:
            self.predicted_bbox = self.bbox
            return
        
        # Extrapolate position (assuming 30 FPS)
        frames_ahead = horizon_seconds * 30
        pred_x = self.bbox[0] + vx * frames_ahead
        pred_y = self.bbox[1] + vy * frames_ahead
        
        self.predicted_bbox = (int(pred_x), int(pred_y), self.bbox[2], self.bbox[3])


class ObjectManager:
    """
    Manages multiple tracked objects with unique identities and audio signatures.
    """
    
    def __init__(self):
        """Initialize the object manager."""
        self.objects: List[TrackedObject] = []
        self.next_id = 0
        self.color_palette = [
            (255, 0, 0),    # Blue
            (0, 255, 0),    # Green
            (0, 0, 255),    # Red
            (255, 255, 0),  # Cyan
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Yellow
        ]
        print("📦 ObjectManager initialized.")
    
    def add_object(self, label, bbox, confidence=1.0, context=None):
        """
        Add a new object to track.
        
        Args:
            label: Object type (e.g., "person", "phone")
            bbox: Bounding box (x, y, w, h)
            confidence: Detection confidence
            context: Semantic context (e.g., "on table")
        
        Returns:
            TrackedObject instance
        """
        # Get audio signature for this object type
        audio_sig = config.AUDIO_SIGNATURES.get(label, config.AUDIO_SIGNATURES["default"])
        
        # Assign color
        color = self.color_palette[self.next_id % len(self.color_palette)]
        
        # Create object
        obj = TrackedObject(
            id=self.next_id,
            label=label,
            bbox=bbox,
            tracker=None,
            confidence=confidence,
            audio_signature=audio_sig,
            color=color,
            last_update=time.time(),
            threat_score=0.0,
            is_lost=False,
            lost_time=None,
            template=None,
            last_template_update=0.0,
            context=context,
            last_verified=time.time()
        )
        
        self.objects.append(obj)
        self.next_id += 1
        
        print(f"➕ Added object #{obj.id}: {label} at {bbox}")
        return obj
    
    def remove_object(self, obj_id):
        """Remove an object by ID."""
        self.objects = [obj for obj in self.objects if obj.id != obj_id]
        print(f"➖ Removed object #{obj_id}")
    
    def get_object(self, obj_id):
        """Get object by ID."""
        for obj in self.objects:
            if obj.id == obj_id:
                return obj
        return None
    
    def get_objects_by_label(self, label):
        """Get all objects matching a label."""
        return [obj for obj in self.objects if obj.label.lower() == label.lower()]
    
    def clear(self):
        """Clear all tracked objects."""
        self.objects.clear()
        print("🗑️ Cleared all objects.")
    
    def update_trackers(self, frame):
        """
        Update all object trackers with a new frame.
        
        Args:
            frame: New video frame
        
        Returns:
            List of successfully tracked objects
        """
        # Early exit if no objects to track
        if not self.objects:
            return []
        
        tracked = []
        failed = []
        
        for obj in self.objects:
            # Skip if tracker not initialized
            if obj.tracker is None:
                if not obj.is_lost:
                    obj.is_lost = True
                    obj.lost_time = time.time()
                continue
                
            try:
                ok, bbox = obj.tracker.update(frame)
                if ok:
                    obj.update_velocity(bbox)
                    obj.is_lost = False
                    obj.lost_time = None
                    
                    # Predict future position if enabled
                    if config.MOTION_PREDICTION_ENABLED:
                        obj.predict_position(config.PREDICTION_HORIZON_SECONDS)
                    
                    # === THREAT SCORE CALCULATION ===
                    # 1. Base Score: Proximity (Size)
                    area = bbox[2] * bbox[3]
                    frame_area = frame.shape[0] * frame.shape[1]
                    size_score = min(1.0, area / (frame_area * 0.5)) # Cap at 50% screen coverage
                    
                    # 2. Semantic Score: Type Importance
                    # Normalize label to lowercase for lookup
                    label_key = obj.label.lower().split(" ")[-1] # Handle "Red Cup" -> "cup"
                    semantic_score = config.THREAT_PRIORITIES.get(label_key, config.THREAT_PRIORITIES["default"])
                    
                    # 3. Centrality Score: Is it in front of us?
                    center_x = bbox[0] + bbox[2] / 2
                    frame_center_x = frame.shape[1] / 2
                    dist_from_center = abs(center_x - frame_center_x) / (frame.shape[1] / 2)
                    centrality_score = 1.0 - min(1.0, dist_from_center)
                    
                    obj.threat_score = (size_score * 0.7) + (centrality_score * 0.3)
                    
                    tracked.append(obj)
                else:
                    # Tracker failed
                    if not obj.is_lost:
                        print(f"⚠️ Tracker lost for object #{obj.id} ({obj.label})")
                        obj.is_lost = True
                        obj.lost_time = time.time()
                    failed.append(obj)
            except Exception as e:
                print(f"⚠️ Tracker error for object #{obj.id}: {e}")
                failed.append(obj)
        
        # We return tracked objects, but we keep lost ones in self.objects for a while
        return tracked
    
    def init_tracker(self, obj_id, frame):
        """
        Initialize a tracker for an object.
        
        Args:
            obj_id: Object ID
            frame: Video frame to initialize from
        """
        obj = self.get_object(obj_id)
        if obj and obj.bbox:
            # Robust tracker initialization (optional - requires opencv-contrib-python)
            try:
                # Try standard OpenCV 4+
                if hasattr(cv2, 'TrackerCSRT_create'):
                    obj.tracker = cv2.TrackerCSRT_create()
                # Try legacy (OpenCV 4.5+)
                elif hasattr(cv2, 'legacy') and hasattr(cv2.legacy, 'TrackerCSRT_create'):
                    obj.tracker = cv2.legacy.TrackerCSRT_create()
                # Fallback to KCF (faster but less accurate)
                elif hasattr(cv2, 'TrackerKCF_create'):
                    print("⚠️ CSRT not found, falling back to KCF")
                    obj.tracker = cv2.TrackerKCF_create()
                else:
                    # Trackers not available - detection-only mode (requires opencv-contrib-python for tracking)
                    obj.tracker = None
                    return
                
                obj.tracker.init(frame, obj.bbox)
                print(f"🎯 Initialized tracker for object #{obj_id} ({obj.label})")
            except Exception as e:
                print(f"❌ Failed to init tracker: {e}")
    
    def init_all_trackers(self, frame):
        """Initialize trackers for all objects."""
        for obj in self.objects:
            if not obj.tracker:
                self.init_tracker(obj.id, frame)
    
    def get_closest_object(self, frame_width, frame_height):
        """
        Get the object closest to the camera (largest bbox).
        
        Returns:
            TrackedObject or None
        """
        if not self.objects:
            return None
        
        max_area = 0
        closest = None
        
        for obj in self.objects:
            if obj.bbox:
                area = obj.bbox[2] * obj.bbox[3]
                if area > max_area:
                    max_area = area
                    closest = obj
        
        return closest
    
    def get_centered_object(self, frame_width, frame_height):
        """
        Get the object closest to the center of the frame.
        
        Returns:
            TrackedObject or None
        """
        if not self.objects:
            return None
        
        center_x = frame_width / 2
        center_y = frame_height / 2
        
        min_dist = float('inf')
        centered = None
        
        for obj in self.objects:
            if obj.bbox:
                obj_center_x = obj.bbox[0] + obj.bbox[2] / 2
                obj_center_y = obj.bbox[1] + obj.bbox[3] / 2
                
                dist = np.sqrt((obj_center_x - center_x)**2 + (obj_center_y - center_y)**2)
                
                if dist < min_dist:
                    min_dist = dist
                    centered = obj
        
        return centered
    
    def filter_by_labels(self, labels):
        """
        Keep only objects matching the given labels.
        
        Args:
            labels: List of label strings
        """
        labels_lower = [l.lower() for l in labels]
        self.objects = [obj for obj in self.objects if obj.label.lower() in labels_lower]
    
    def limit_objects(self, max_count):
        """
        Limit the number of tracked objects (keep most confident).
        
        Args:
            max_count: Maximum number of objects to keep
        """
        if len(self.objects) > max_count:
            # Sort by confidence, keep top N
            self.objects.sort(key=lambda o: o.confidence, reverse=True)
            removed = self.objects[max_count:]
            self.objects = self.objects[:max_count]
            
            print(f"⚠️ Limited to {max_count} objects, removed {len(removed)}")
    
    def get_proximity_zone(self, obj, frame_width, frame_height):
        """
        Determine which proximity zone an object is in.
        
        Args:
            obj: TrackedObject
            frame_width, frame_height: Frame dimensions
        
        Returns:
            Zone name ("safe", "caution", "warning")
        """
        if not obj.bbox:
            return "safe"
        
        # Calculate object size relative to frame
        obj_area = obj.bbox[2] * obj.bbox[3]
        frame_area = frame_width * frame_height
        size_ratio = obj_area / frame_area
        
        for zone_name, zone_config in config.PROXIMITY_ZONES.items():
            if zone_config["min"] <= size_ratio < zone_config["max"]:
                return zone_name
        
        return "safe"

    def update_template(self, obj, frame):
        """
        Update the visual template for an object.
        Should be called periodically (e.g. every 1s) when tracking is good.
        """
        if not obj.bbox:
            return
            
        x, y, w, h = map(int, obj.bbox)
        
        # Ensure within bounds
        h_frame, w_frame = frame.shape[:2]
        x = max(0, min(x, w_frame - 1))
        y = max(0, min(y, h_frame - 1))
        w = max(1, min(w, w_frame - x))
        h = max(1, min(h, h_frame - y))
        
        if w < 10 or h < 10:
            return
            
        template = frame[y:y+h, x:x+w]
        obj.template = template
        obj.last_template_update = time.time()
        # print(f"📸 Updated template for #{obj.id}")

    def compute_iou(self, box1, box2):
        """Compute Intersection over Union (IoU) between two boxes."""
        x1, y1, w1, h1 = box1
        x2, y2, w2, h2 = box2
        
        xA = max(x1, x2)
        yA = max(y1, y2)
        xB = min(x1 + w1, x2 + w2)
        yB = min(y1 + h1, y2 + h2)
        
        interArea = max(0, xB - xA) * max(0, yB - yA)
        box1Area = w1 * h1
        box2Area = w2 * h2
        
        if float(box1Area + box2Area - interArea) == 0:
            return 0.0
            
        iou = interArea / float(box1Area + box2Area - interArea)
        return iou

    def cleanup_stale_trackers(self, max_age=30.0):
        """Remove objects not verified by Gemini for max_age seconds."""
        now = time.time()
        active_count = len(self.objects)
        
        self.objects = [obj for obj in self.objects 
                       if (now - obj.last_verified) < max_age]
        
        removed = active_count - len(self.objects)
        if removed > 0:
            print(f"🧹 Removed {removed} stale trackers (>{max_age}s without verification)")
            return True # Return True if cleanup happened
        return False
