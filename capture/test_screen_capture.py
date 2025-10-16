import time

import mss

from capture.recorder import Recorder
from capture.screen_capture import create_capture, get_available_monitors


def main():
    available_monitors = get_available_monitors()

    recorders: list[Recorder] = []
    for idx, name in available_monitors.items():
        capture = create_capture(idx, name)
        recorder = Recorder(capture)
        recorders.append(recorder)
        recorder.start()
    time.sleep(20)
    for recorder in recorders:
        recorder.stop()
