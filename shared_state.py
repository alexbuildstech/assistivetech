import threading
import copy
import time
from collections import deque

class SharedGameState:
    """
    Thread-safe shared state optimized for ultra-low latency real-time processing.
    Minimizes lock contention and eliminates unnecessary memory copies.
    """
    def __init__(self):
        # Use RLock for reentrant locking (safer for nested calls)
        self._lock = threading.RLock()
        
        # Frame storage - use memory-efficient approach
        self._frame_buffer = None  # Pre-allocated buffer
        self._frame_id = 0
        self._frame_timestamp = 0.0
        self._last_processed_id = -1
        
        # Tracking state
        self._tracked_objects = []
        self._tracking_status = "READY"
        
        # Command queue with maxlen to prevent memory bloat
        self._command_queue = deque(maxlen=5)  # Reduced for lower latency
        
        # System state
        self.is_running = True
        self._fps = 0.0
        
        # Performance metrics
        self._dropped_frames = 0
        self._lock_contention_count = 0
        
        # Pre-allocated display state dict to avoid recreation
        self._display_state_cache = {
            "frame": None,
            "objects": [],
            "status": "READY",
            "fps": 0.0
        }

    @property
    def lock(self):
        return self._lock
        
    def update_frame(self, frame):
        """
        Update frame with minimal locking.
        Simply swaps the reference - no copy.
        """
        # Quick check without lock
        if frame is None:
            return
            
        with self._lock:
            self._frame_buffer = frame
            self._frame_id += 1
            self._frame_timestamp = time.time()
            
    def get_latest_frame(self, mark_processed=True):
        """
        Get latest frame optimized for vision thread.
        Returns None if no new frame available (prevents duplicate processing).
        """
        with self._lock:
            if self._frame_buffer is None:
                return None
                
            # Check if this frame is new
            if self._frame_id <= self._last_processed_id:
                self._dropped_frames += 1
                return None
            
            frame = self._frame_buffer
            
            if mark_processed:
                self._last_processed_id = self._frame_id
                
            return frame
            
    def peek_frame(self):
        """Non-blocking peek at current frame."""
        with self._lock:
            return self._frame_buffer
            
    def update_tracking(self, objects, status):
        """Update tracking with reference swap (no deep copy)."""
        with self._lock:
            # Just swap the reference - objects are immutable enough for this
            self._tracked_objects = objects
            self._tracking_status = status
            
    def get_tracking_state(self):
        """Get current tracking state efficiently."""
        with self._lock:
            return self._tracked_objects, self._tracking_status
            
    def get_display_state(self):
        """Get display state - creates minimal copy for UI thread."""
        with self._lock:
            # Update cache in place
            self._display_state_cache["frame"] = self._frame_buffer
            self._display_state_cache["objects"] = self._tracked_objects
            self._display_state_cache["status"] = self._tracking_status
            self._display_state_cache["fps"] = self._fps
            return self._display_state_cache.copy()
            
    def add_command(self, command):
        """Add command with immediate dispatch if queue full (drop old)."""
        with self._lock:
            # If queue is full, drop oldest (newest commands matter most)
            if len(self._command_queue) >= 5:
                try:
                    self._command_queue.popleft()
                except IndexError:
                    pass
            self._command_queue.append(command)
            
    def get_next_command(self):
        """Get next command - O(1) with deque."""
        with self._lock:
            if self._command_queue:
                return self._command_queue.popleft()
            return None
            
    def has_commands(self):
        """Fast check if commands pending."""
        with self._lock:
            return len(self._command_queue) > 0
            
    def set_fps(self, fps):
        """Update FPS counter."""
        with self._lock:
            self._fps = fps
            
    def get_stats(self):
        """Get performance metrics."""
        with self._lock:
            return {
                "frame_id": self._frame_id,
                "last_processed": self._last_processed_id,
                "dropped_frames": self._dropped_frames,
                "pending_commands": len(self._command_queue),
                "tracked_objects": len(self._tracked_objects),
                "fps": self._fps
            }
