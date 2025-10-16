import time

from capture.recorder import Recorder
from capture.camera_capture import CameraCapture, get_available_cameras


def main():
    available_cameras = get_available_cameras()
    print("Available cameras:", available_cameras)
    recorders: list[Recorder] = []
    open_idx = [0]
    for idx in open_idx:
        try:
            capture = CameraCapture(idx, available_cameras[idx])
            recorder = Recorder(capture)
            recorders.append(recorder)
            recorder.start()
        except ValueError as e:
            print(e)
    time.sleep(20)
    for recorder in recorders:
        recorder.stop()


if __name__ == "__main__":
    main()
