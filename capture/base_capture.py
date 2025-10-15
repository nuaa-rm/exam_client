import numpy as np


class BaseCapture:
    def __init__(self, name: str, width: int, height: int, fps: int = 24):
        self.name = name
        self.width = width
        self.height = height
        self.fps = fps
        self.auto_wait = False

    def capture_frame(self) -> np.ndarray:
        """Capture a single frame and return it as a numpy array."""
        raise NotImplementedError("Subclasses must implement this method.")
    
    def stop(self):
        """Release any resources if needed."""
        pass

