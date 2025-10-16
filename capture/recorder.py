from threading import Thread, Event, Lock
from pathlib import Path
import time
import atexit

import av
import cv2

from capture.accel_utils import select_best_encoder, get_encoder_options
from capture.base_capture import BaseCapture
from utils.logger import getLogger


class Recorder:
    def __init__(self, capture: BaseCapture, preferred_encoder=None):
        self.capture = capture
        self.output_path = Path('./media') / self.capture.name
        self.preferred_encoder = preferred_encoder
        self.recording = False
        self.stop_event = Event()
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        # 配置 logger
        self.logger = getLogger(f"Recorder.{self.capture.name}")
        
        # 保存最新的3个切片编号
        self.latest_segments = []
        # 用于保护 latest_segments 的锁
        self.segments_lock = Lock()
        
        # 注册退出时的清理函数
        atexit.register(self._cleanup)
        
        # 计算下一个切片的起始编号
        self.start_segment_number = 0
        existing_segments = list(self.output_path.glob('video_*.ts'))
        if existing_segments:
            # 从现有切片中找到最大编号
            segment_numbers = []
            for seg in existing_segments:
                try:
                    num = int(seg.stem.split('_')[1])
                    segment_numbers.append(num)
                except (ValueError, IndexError):
                    pass
            if segment_numbers:
                self.start_segment_number = max(segment_numbers) + 1
                self.latest_segments.append(self.start_segment_number - 1)
        
    def start(self):
        selected_encoder = select_best_encoder()
        self.logger.info(f"使用编码器: {selected_encoder}")
        self.logger.info(f"切片起始编号: {self.start_segment_number}")
        
        hls_options = {
            'hls_time': '3',  # 单个切片时长（秒）
            'hls_list_size': '0',  # 保留所有切片
            'hls_flags': 'append_list+independent_segments',  # 追加到现有列表，确保每个切片独立可播放
            'hls_segment_type': 'mpegts',  # 使用 mpegts 格式
            'hls_segment_filename': str(self.output_path / 'video_%d.ts'),
        }
        self.output_container = av.open(self.output_path / 'video.m3u8', mode='w', format='hls', options=hls_options)
        stream = self.output_container.add_stream(selected_encoder, rate=self.capture.fps)
        if not isinstance(stream, av.VideoStream):
            raise RuntimeError("无法创建视频流")
        self.stream = stream
        self.stream.width = self.capture.width
        self.stream.height = self.capture.height
        
        # 设置像素格式
        if 'nvenc' in selected_encoder or 'qsv' in selected_encoder:
            self.stream.pix_fmt = 'nv12'
        else:
            self.stream.pix_fmt = 'yuv420p'
        
        # 设置编码参数
        encoder_options = get_encoder_options(selected_encoder)
        # 添加关键帧间隔设置（GOP），HLS 需要定期的关键帧来分割切片
        encoder_options['g'] = str(self.capture.fps * 3)  # 每 2 秒一个关键帧
        self.stream.options = encoder_options
        
        self.recording = True
        self.stop_event.clear()
        self.recording_thread = Thread(target=self._record_screen, daemon=True)
        self.recording_thread.start()
        
        # 启动切片监控线程
        self.monitor_thread = Thread(target=self._monitor_segments, daemon=True)
        self.monitor_thread.start()
        
    def _record_screen(self):
        frame_count = 0
        while not self.stop_event.is_set():
            start_time = time.time()
            frame_count += 1
            
            # 捕获屏幕
            capture_start = time.time()
            frame_array = self.capture.capture_frame()
            capture_time = time.time() - capture_start
            
            # 转换为合适的颜色空间
            convert_start = time.time()
            if self.stream.pix_fmt == 'nv12':
                frame_yuv = cv2.cvtColor(frame_array, cv2.COLOR_BGR2YUV_I420)
                av_frame = av.VideoFrame.from_ndarray(frame_yuv, format='yuv420p') # type: ignore
            else:
                frame_rgb = cv2.cvtColor(frame_array, cv2.COLOR_BGR2RGB)
                av_frame = av.VideoFrame.from_ndarray(frame_rgb, format='rgb24') # type: ignore
            convert_time = time.time() - convert_start
            
            # 编码并写入
            encode_start = time.time()
            for packet in self.stream.encode(av_frame):
                if self.output_container:
                    self.output_container.mux(packet)
            encode_time = time.time() - encode_start
            
            # 控制帧率
            if not self.capture.auto_wait:
                elapsed = time.time() - start_time
                sleep_time = max(0, 1 / self.capture.fps - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

            # 性能监控（可选）
            if frame_count % 100 == 0:
                elapsed = time.time() - start_time
                fps_actual = 1.0 / elapsed if elapsed > 0 else 0
                self.logger.debug(
                    f"帧 {frame_count} 性能统计: "
                    f"截图={capture_time*1000:.2f}ms, "
                    f"转换={convert_time*1000:.2f}ms, "
                    f"编码={encode_time*1000:.2f}ms, "
                    f"总计={elapsed*1000:.2f}ms, "
                    f"实际帧率={fps_actual:.2f}fps"
                )
        if hasattr(self, 'capture') and self.capture:
            self.capture.stop()
    
    def _monitor_segments(self):
        """监控切片文件，每3秒检查一次新生成的切片"""
        current_check_number = self.start_segment_number
        path = Path(self.output_path)
        
        while not self.stop_event.is_set():
            # 从当前编号+1开始向后查找
            check_number = current_check_number + 1
            found_new = False
            
            while True:
                segment_file = path.parent / f'monitor_{check_number}.ts'
                if segment_file.exists():
                    # 找到新切片，添加到列表（使用锁保证线程安全）
                    with self.segments_lock:
                        self.latest_segments.append(check_number)
                        # 保持数组长度为3
                        if len(self.latest_segments) > 3:
                            self.latest_segments.pop(0)
                    
                    current_check_number = check_number
                    check_number += 1
                    found_new = True
                else:
                    # 没有找到文件，停止查找
                    break
            
            if found_new:
                with self.segments_lock:
                    self.logger.debug(f"检测到新切片，最新切片编号: {self.latest_segments}")
            
            # 等待3秒后再次检查
            time.sleep(3)
    
    def get_latest_segments(self):
        """
        获取最新的切片编号列表（线程安全）
        
        Returns:
            list: 最新的切片编号列表（最多3个）
        """
        with self.segments_lock:
            return self.latest_segments.copy()
    
    def generate_live_m3u8(self):
        """
        基于最新的切片生成直播形式的 m3u8 文件内容
        
        Returns:
            str: m3u8 格式的播放列表内容
        """
        latest_segments = self.get_latest_segments()
        
        if not latest_segments:
            # 如果没有切片,返回空的 m3u8
            return "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:3\n"
        
        # 构建 m3u8 内容
        m3u8_lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:3",
            "#EXT-X-TARGETDURATION:3",  # 每个切片的目标时长
            f"#EXT-X-MEDIA-SEQUENCE:{latest_segments[0]}",  # 第一个切片的序号
        ]
        
        # 添加每个切片
        for segment_num in latest_segments:
            m3u8_lines.append("#EXTINF:3.0,")  # 切片时长
            m3u8_lines.append(f"video_{segment_num}.ts")
        
        # 注意: 不添加 #EXT-X-ENDLIST,因为这是直播流,还在继续生成
        
        return "\n".join(m3u8_lines) + "\n"
                    
    def stop(self):
        self.stop_event.set()
        if hasattr(self, 'recording_thread') and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=5.0)  # 设置超时时间，避免无限等待
        if hasattr(self, 'monitor_thread') and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)  # 等待监控线程结束
            
        self._cleanup()

    def __del__(self):
        self.stop()

    def _cleanup(self):
        if self.recording is False:
            return
        self.recording = False
        self.logger.info("开始清理资源")
        
        # 停止捕获
        if hasattr(self, 'capture') and self.capture:
            try:
                self.capture.stop()
                self.logger.info("捕获已停止")
            except Exception as e:
                self.logger.error(f"停止捕获时出错: {e}", exc_info=True)
        
        # 刷新并关闭输出容器
        if hasattr(self, 'output_container') and self.output_container:
            try:
                # 刷新编码器
                if hasattr(self, 'stream'):
                    for packet in self.stream.encode():
                        self.output_container.mux(packet)
                self.logger.info("编码器已刷新")
            except Exception as e:
                self.logger.error(f"刷新编码器时出错: {e}", exc_info=True)
            
            try:
                self.output_container.close()
                self.logger.info("输出容器已关闭")
            except Exception as e:
                self.logger.error(f"关闭输出容器时出错: {e}", exc_info=True)
            finally:
                self.output_container = None
