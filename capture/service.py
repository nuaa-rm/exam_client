from capture.recorder import Recorder
from capture.screen_capture import create_capture
from capture.camera_capture import CameraCapture


recorders = {}

def start_screen_recording(monitor_idx: int, monitor_name: str, fps: int = 24):
    capture = create_capture(monitor_idx, monitor_name, fps)
    recorder = Recorder(capture)
    recorders[recorder.name] = recorder
    recorder.start()
    return recorder


def start_camera_recording(camera_idx: int, camera_name: str, fps: int = 24):
    capture = CameraCapture(camera_idx, camera_name, fps)
    recorder = Recorder(capture)
    recorders[recorder.name] = recorder
    recorder.start()
    return recorder


def get_recorder_names():
    return list(recorders.keys())


def get_recorder(name: str) -> Recorder | None:
    return recorders.get(name)
