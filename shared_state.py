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
        self._lock = threading.RLock()
        self._frame_buffer = None
        self._frame_id = 0
        self._frame_timestamp = 0.0
        self._last_processed_id = -1
        self._tracked_objects = []
        self._tracking_status = "READY"
        self._command_queue = deque(maxlen=5)
        self.is_running = True
        self._fps = 0.0
        self._dropped_frames = 0
        self._lock_contention_count = 0
        self._display_state_cache = {
            "frame": None,
            "objects": [],
            "status": "READY",
            "fps": 0.0,
        }

    @property
    def lock(self):
        return self._lock

    def update_frame(self, frame):
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
        Returns a copy to prevent mutation of the shared buffer.
        """
        with self._lock:
            if self._frame_buffer is None:
                return None
            if self._frame_id <= self._last_processed_id:
                self._dropped_frames += 1
                return None
            frame = self._frame_buffer.copy()
            if mark_processed:
                self._last_processed_id = self._frame_id
            return frame

    def peek_frame(self):
        with self._lock:
            return self._frame_buffer

    def update_tracking(self, objects, status):
        with self._lock:
            self._tracked_objects = list(objects)
            self._tracking_status = status

    def get_tracking_state(self):
        with self._lock:
            return list(self._tracked_objects), self._tracking_status

    def get_display_state(self):
        with self._lock:
            self._display_state_cache["frame"] = self._frame_buffer
            self._display_state_cache["objects"] = copy.deepcopy(self._tracked_objects)
            self._display_state_cache["status"] = self._tracking_status
            self._display_state_cache["fps"] = self._fps
            return self._display_state_cache.copy()

    def add_command(self, command):
        with self._lock:
            if len(self._command_queue) >= 5:
                try:
                    self._command_queue.popleft()
                except IndexError:
                    pass
            self._command_queue.append(command)

    def get_next_command(self):
        with self._lock:
            if self._command_queue:
                return self._command_queue.popleft()
            return None

    def has_commands(self):
        with self._lock:
            return len(self._command_queue) > 0

    def set_fps(self, fps):
        with self._lock:
            self._fps = fps

    def get_stats(self):
        with self._lock:
            return {
                "frame_id": self._frame_id,
                "last_processed": self._last_processed_id,
                "dropped_frames": self._dropped_frames,
                "pending_commands": len(self._command_queue),
                "tracked_objects": len(self._tracked_objects),
                "fps": self._fps,
            }
