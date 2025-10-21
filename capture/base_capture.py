import numpy as np


def process_name(name: str, idx: int) -> str:
    # 检测是否包含非ASCII字符
    has_non_ascii = any(ord(char) >= 128 for char in name)
    
    # 替换非ASCII字符为下划线
    processed_name = ''.join(char if ord(char) < 128 else '_' for char in name)
    
    # 如果包含非ASCII字符，添加原名称hash值的最后4位
    if has_non_ascii:
        processed_name = f"{processed_name}_{idx}"
    
    return processed_name


class BaseCapture:
    def __init__(self, name: str, idx: int, width: int, height: int, fps: int = 24):
        self.name = process_name(name, idx)
        
        self.width = width
        self.height = height
        self.idx = idx
        self.fps = fps
        self.auto_wait = False

    def capture_frame(self) -> np.ndarray:
        """Capture a single frame and return it as a numpy array."""
        raise NotImplementedError("Subclasses must implement this method.")
    
    def stop(self):
        """Release any resources if needed."""
        pass

