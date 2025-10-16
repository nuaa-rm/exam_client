import numpy as np


class BaseCapture:
    def __init__(self, name: str, width: int, height: int, fps: int = 24):
        # 检测是否包含非ASCII字符
        has_non_ascii = any(ord(char) >= 128 for char in name)
        
        # 替换非ASCII字符为下划线
        self.name = ''.join(char if ord(char) < 128 else '_' for char in name)
        
        # 如果包含非ASCII字符，添加原名称hash值的最后4位
        if has_non_ascii:
            hash_suffix = str(abs(hash(name)))[-4:]
            self.name = f"{self.name}_{hash_suffix}"
        
        self.width = width
        self.height = height
        self.fps = fps
        self.auto_wait = False

    def capture_frame(self) -> np.ndarray:
        """Capture a single frame and return it as a numpy array."""
        raise NotImplementedError("Subclasses must implement this method.")
    
    def stop(self):
        """Release any resources if needed."""
        pass

