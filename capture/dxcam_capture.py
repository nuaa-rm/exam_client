import re
import dxcam
import numpy as np

from capture.base_capture import BaseCapture


class DxcamCapture(BaseCapture):
    def __init__(self, idx: int, name: str, fps: int = 24):
        self.camera = None
        output_info_str = dxcam.output_info()
        
        # 使用正则表达式解析输出信息，生成字典: {output编号: {"device": device编号, "resolution": (width, height)}}
        # 匹配格式: Device[0] Output[1]: Res:(1920, 1080) Rot:0 Primary:False
        pattern = r'Device\[(\d+)\]\s+Output\[(\d+)\]:\s+Res:\((\d+),\s*(\d+)\)'
        output_dict = {}
        
        for match in re.finditer(pattern, output_info_str):
            device_idx = int(match.group(1))
            output_idx = int(match.group(2))
            width = int(match.group(3))
            height = int(match.group(4))
            
            output_dict[output_idx] = {
                "device": device_idx,
                "resolution": (width, height)
            }
        
        # 获取当前 idx 对应的信息
        if idx not in output_dict:
            raise ValueError(f"无法找到 Output[{idx}] 的信息")
        
        device_idx = output_dict[idx]["device"]
        width, height = output_dict[idx]["resolution"]

        super().__init__(name, width, height, fps)
        self.camera = dxcam.create(device_idx=device_idx, output_idx=idx, output_color="BGR")
        if self.camera is None:
            raise ValueError(f"无法创建 Dxcam 设备，索引: {idx}")
        self.auto_wait = True
        self.start = False

    def capture_frame(self) -> np.ndarray:
        """Capture a single frame and return it as a numpy array."""
        if self.camera is None:
            raise RuntimeError("DxCam未初始化")
        if self.start is False:
            self.camera.start(target_fps=self.fps, video_mode=True)
            self.start = True
        return self.camera.get_latest_frame()

    def stop(self):
        if self.camera:
            self.camera.stop()
            self.start = False

    def __del__(self):
        if self.camera:
            self.camera.release()
