import mss
import wmi

from capture.dxcam_capture import DxcamCapture
from capture.mss_capture import MssCapture
from capture.base_capture import BaseCapture


def create_capture(idx: int, name: str, fps: int = 24) -> BaseCapture:
    try:
        dxcam = DxcamCapture(idx, name, fps)
        dxcam.capture_frame()
        dxcam.stop()
        return dxcam
    except Exception:
        pass
    print("Falling back to mss capture")
    return MssCapture(idx, name, fps)


def get_available_monitors() -> dict[int, str]:
    with mss.mss() as sct:
        monitors = sct.monitors

    objs = wmi.WMI().Win32_PnPEntity(ConfigManagerErrorCode=0)
    displays = [x for x in objs if 'Monitor' in str(x) and 'DISPLAY' in str(x)]
    if len(displays) != len(monitors) - 1:
        return {i: f"Monitor_{i}" for i in range(len(monitors) - 1)}

    return {i: displays[len(displays) - 1 - i].name for i in range(len(displays))}
