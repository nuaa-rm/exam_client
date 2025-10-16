import mss
import cv2
import numpy as np

from capture.base_capture import BaseCapture


class MssCapture(BaseCapture):
    def __init__(self, idx: int, name: str, fps: int = 24):
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[idx + 1]
        self.sct.close()
        self.sct = None
        super().__init__(name, self.monitor["width"], self.monitor["height"], fps)

    def capture_frame(self) -> np.ndarray:
        """Capture a single frame and return it as a numpy array."""
        if self.sct is None:
            self.sct = mss.mss()
        screenshot = self.sct.grab(self.monitor)
        frame_array = np.array(screenshot)
        
        return cv2.cvtColor(frame_array, cv2.COLOR_BGRA2BGR)
    
    def stop(self):
        if self.sct:
            self.sct.close()
            self.sct = None

    def __del__(self):
        if self.sct:
            self.sct.close()
