import cv2
import numpy as np

from pygrabber.dshow_graph import FilterGraph

from capture.base_capture import BaseCapture


class CameraCapture(BaseCapture):
    def __init__(self, idx: int, name: str, fps: int = 24):
        self.idx = idx
        self.cap = cv2.VideoCapture(idx)
        if not self.cap.isOpened():
            raise ValueError(f"无法打开摄像头索引 {idx}")
        
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        super().__init__(name, width, height, fps)

    def capture_frame(self) -> np.ndarray:
        """Capture a single frame and return it as a numpy array."""
        if not self.cap:
            self.cap = cv2.VideoCapture(self.idx)
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError("无法从摄像头读取帧")
        return frame
    
    def stop(self):
        if self.cap and self.cap.isOpened():
            self.cap.release()
            self.cap = None

    def __del__(self):
        if self.cap and self.cap.isOpened():
            self.cap.release()


def get_available_cameras() :
    devices = FilterGraph().get_input_devices()

    available_cameras = {}

    for device_index, device_name in enumerate(devices):
        available_cameras[device_index] = device_name

    return available_cameras
