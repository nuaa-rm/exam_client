from threading import Thread
import time

from capture.recorder import Recorder
from capture.base_capture import process_name
from capture.screen_capture import create_capture
from capture.camera_capture import CameraCapture
from utils.logger import getLogger


recorders : dict[str, Recorder] = {}
screens = []
cameras = []
logger = getLogger("recorder.service")

def start_screen_recording(monitor_idx: int, monitor_name: str, fps: int = 24):
    monitor_name = process_name(monitor_name, monitor_idx)
    if monitor_name in screens:
        return recorders[monitor_name]
    capture = create_capture(monitor_idx, monitor_name, fps)
    capture.capture_frame()
    recorder = Recorder(capture)
    recorders[recorder.name] = recorder
    screens.append(recorder.name)
    recorder.start()
    return recorder


def start_camera_recording(camera_idx: int, camera_name: str, fps: int = 24):
    camera_name = process_name(camera_name, camera_idx)
    if camera_name in cameras:
        return recorders[camera_name]
    capture = CameraCapture(camera_idx, camera_name, fps)
    capture.capture_frame()
    recorder = Recorder(capture)
    recorders[recorder.name] = recorder
    cameras.append(recorder.name)
    recorder.start()
    return recorder


def _cleanup_recorders():
    while True:
        to_remove = []
        for name, recorder in recorders.items():
            if not recorder.recording:
                recorder.stop()
                to_remove.append(name)
        for name in to_remove:
            logger.info(f"清理录制器: {name}")
            del recorders[name]
            if name in screens:
                screens.remove(name)
            if name in cameras:
                cameras.remove(name)
        time.sleep(5)

            
cleanup_thread = Thread(target=_cleanup_recorders, daemon=True)
cleanup_thread.start()


def get_recorder_names():
    return {'screen': screens, 'camera': cameras}


def get_recorder(name: str) -> Recorder | None:
    return recorders.get(name)


def health() -> bool:
    screen_ok = all(recorders[recorder].recording for recorder in screens)
    camera_ok = all(recorders[recorder].recording for recorder in cameras)
    logger.debug(f"Health check - Screens: {screens}, Cameras: {cameras}, Recorders: {list(recorders.keys())}")
    return screen_ok and camera_ok and len(cameras) > 0 and len(screens) > 0 and len(recorders) == len(screens) + len(cameras)
