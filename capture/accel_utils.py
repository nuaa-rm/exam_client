import av


def check_hardware_acceleration() -> list[tuple[str, str]]:
    """检测系统可用的硬件加速器"""
    codecs = av.codecs_available
    hardware_encoders = []
    
    # 检查NVIDIA NVENC
    if 'h264_nvenc' in codecs:
        hardware_encoders.append(('h264_nvenc', 'NVIDIA NVENC'))
    if 'hevc_nvenc' in codecs:
        hardware_encoders.append(('hevc_nvenc', 'NVIDIA NVENC HEVC'))
    
    # 检查Intel QSV
    if 'h264_qsv' in codecs:
        hardware_encoders.append(('h264_qsv', 'Intel Quick Sync'))
    if 'hevc_qsv' in codecs:
        hardware_encoders.append(('hevc_qsv', 'Intel Quick Sync HEVC'))
    
    # 检查AMD AMF
    if 'h264_amf' in codecs:
        hardware_encoders.append(('h264_amf', 'AMD AMF'))
    if 'hevc_amf' in codecs:
        hardware_encoders.append(('hevc_amf', 'AMD AMF HEVC'))
    
    # 检查VAAPI (Linux)
    if 'h264_vaapi' in codecs:
        hardware_encoders.append(('h264_vaapi', 'VAAPI'))
    
    # 检查VideoToolbox (macOS)
    if 'h264_videotoolbox' in codecs:
        hardware_encoders.append(('h264_videotoolbox', 'VideoToolbox'))
    
    return hardware_encoders


def get_encoder_options(encoder: str) -> dict:
        """获取不同编码器的最佳参数"""
        options = {}
        
        if 'nvenc' in encoder:
            options = {
                'preset': 'p4',
                'tune': 'll',
                'rc': 'vbr',
                'cq': '23',
                'maxrate': '2',
                'bufsize': '4',
            }
        elif 'qsv' in encoder:
            options = {
                'preset': 'faster',
                'global_quality': '20',
            }
        elif 'amf' in encoder:
            options = {
                'quality': 'speed',
                'rc': 'vbr_peak',
                'qmin': '18',
                'qmax': '28',
            }
        else:  # 软件编码
            options = {
                'preset': 'ultrafast',
                'tune': 'zerolatency',
                'crf': '20',
            }
            
        return options


def select_best_encoder(preferred_encoder: str | None = None) -> str:
    """自动选择最佳可用编码器"""
    available_encoders = check_hardware_acceleration()
    
    # 如果指定了优先编码器，检查是否可用
    if preferred_encoder:
        for encoder, _ in available_encoders:
            if encoder == preferred_encoder:
                return encoder
    
    # 按优先级选择编码器
    priority_order = [
        'h264_nvenc',    # NVIDIA
        'h264_qsv',      # Intel
        'h264_amf',      # AMD
    ]
    
    for encoder in priority_order:
        for available_encoder, _ in available_encoders:
            if available_encoder == encoder:
                return encoder
    
    # 如果没有硬件编码器，使用软件编码
    return 'libx264'
