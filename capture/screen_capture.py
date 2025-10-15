from capture.dxcam_capture import DxcamCapture
from capture.mss_capture import MssCapture
from capture.base_capture import BaseCapture


def create_capture(idx: int, fps: int = 24) -> BaseCapture:
    try:
        dxcam = DxcamCapture(idx, fps)
        dxcam.capture_frame()
        dxcam.stop()
        return dxcam
    except Exception:
        pass
    print("Falling back to mss capture")
    return MssCapture(idx, fps)
