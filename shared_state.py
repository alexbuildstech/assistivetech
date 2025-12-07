import threading
import copy
import time

class SharedGameState:
    """
    Thread-safe shared state for decoupling Video, Vision, and Audio threads.
    Ensures the UI never freezes while waiting for AI/Tracking.
    """
    def __init__(self):
        self._lock = threading.Lock()
        
        # Latest frame for display (Video Thread writes, UI reads)
        self.latest_frame = None
        self.frame_id = 0
        
        # Latest tracking results (Vision Thread writes, UI/Audio reads)
        self.tracked_objects = []
        self.tracking_status = "READY"  # READY, SEARCHING, TRACKING, LOST
        
        # Command queue (UI writes, Vision reads)
        self.command_queue = []
        
        # System status
        self.is_running = True
        self.fps = 0.0

    @property
    def lock(self):
        return self._lock
        
    def update_frame(self, frame):
        """Update the latest video frame."""
        with self._lock:
            self.latest_frame = frame
            self.frame_id += 1
            
    def get_latest_frame(self):
        """Get the latest frame for processing."""
        with self._lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None
            
    def update_tracking(self, objects, status):
        """Update tracking results."""
        with self._lock:
            # Shallow copy of list - objects themselves are safe to share
            self.tracked_objects = list(objects)
            self.tracking_status = status
            
    def get_display_state(self):
        """Get all data needed for UI rendering in one atomic operation."""
        with self._lock:
            return {
                "frame": self.latest_frame,
                "objects": self.tracked_objects,
                "status": self.tracking_status,
                "fps": self.fps
            }
            
    def add_command(self, command):
        """Add a command for the vision thread (e.g., "detect")."""
        with self._lock:
            self.command_queue.append(command)
            
    def get_next_command(self):
        """Get next command for vision thread."""
        with self._lock:
            if self.command_queue:
                return self.command_queue.pop(0)
            return None
