import time

import mss

from capture.recorder import Recorder
from capture.screen_capture import create_capture


def main():
    with mss.mss() as sct:
        monitors = sct.monitors
        print(f"检测到 {len(monitors) - 1} 个显示器")

    recorders: list[Recorder] = []
    for idx in range(len(monitors) - 1):
        capture = create_capture(idx)
        recorder = Recorder(capture)
        recorders.append(recorder)
        recorder.start()
    time.sleep(20)
    for recorder in recorders:
        recorder.stop()
