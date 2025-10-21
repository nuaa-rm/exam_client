from threading import Thread, Event, Lock
from pathlib import Path
import time
import atexit
import hashlib

import av
import cv2

from capture.accel_utils import select_best_encoder, get_encoder_options
from capture.base_capture import BaseCapture
from utils.logger import getLogger


class Recorder:
    def __init__(self, capture: BaseCapture, sid: str = "", preferred_encoder=None):
        self.capture = capture
        self.name = capture.name
        self.sid = sid
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
        
        # 签名计数器，每3次运行生成一次签名
        self.sign_counter = 0
        
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
        # 增加错误重试机制：遇到异常最多重试 3 次，仍失败则退出循环并记录错误
        retry_count = 0
        max_retries = 3
        while not self.stop_event.is_set():
            start_time = time.time()
            frame_count += 1

            try:
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

                # 如果成功执行到此，重置重试计数器
                retry_count = 0

            except Exception as e:
                # 记录异常并尝试重试
                retry_count += 1
                self.logger.error(f"录制帧时发生错误 (尝试 {retry_count}/{max_retries}): {e}", exc_info=True)
                if retry_count >= max_retries:
                    self.logger.error(f"连续 {max_retries} 次重试仍失败，停止录制循环。最后错误: {e}")
                    break
                # 小的回退延迟后继续重试
                time.sleep(0.5)
                continue

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
        self.recording = False
        if hasattr(self, 'capture') and self.capture:
            self.capture.stop()
    
    def _monitor_segments(self):
        """监控切片文件，每3秒检查一次新生成的切片"""
        current_check_number = self.start_segment_number
        path = Path(self.output_path)
        # 看门狗：如果连续若干次没有检测到新切片则认为录制已停止或异常，需要自动停止录制
        no_new_counter = 0
        watchdog_threshold = 12  # 连续三次未检测到新切片则触发看门狗

        while not self.stop_event.is_set():
            # 从当前编号+1开始向后查找
            check_number = current_check_number + 1
            found_new = False
            last_segment_number = None
            
            while True:
                segment_file = path / f'video_{check_number}.ts'
                if segment_file.exists():
                    # 找到新切片，添加到列表（使用锁保证线程安全）
                    with self.segments_lock:
                        self.latest_segments.append(check_number)
                        # 保持数组长度为3
                        if len(self.latest_segments) > 3:
                            self.latest_segments.pop(0)
                    
                    current_check_number = check_number
                    last_segment_number = check_number
                    check_number += 1
                    found_new = True
                else:
                    # 没有找到文件，停止查找
                    break
            
            if found_new:
                with self.segments_lock:
                    self.logger.debug(f"检测到新切片，最新切片编号: {self.latest_segments}")
                
                # 签名计数器递增
                self.sign_counter += 1
                
                # 每3次运行生成一次签名
                if self.sign_counter >= 3 and last_segment_number is not None:
                    self._generate_signature(last_segment_number)
                    self.sign_counter = 0  # 重置计数器
                # 重置看门狗计数器
                no_new_counter = 0
            else:
                # 没有检测到新片段，增加看门狗计数
                no_new_counter += 1
                self.logger.debug(f"未检测到新切片，看门狗计数={no_new_counter}/{watchdog_threshold}")

                # 如果连续多次没有新切片，触发自动停止录制
                if no_new_counter >= watchdog_threshold:
                    self.logger.warning(f"看门狗触发：连续 {watchdog_threshold} 次未检测到新切片，自动停止录制。")
                    # 先设置停止事件，通知录制线程结束
                    try:
                        self.stop_event.set()
                    except Exception:
                        pass

                    # 尝试等待录制线程退出，若超时则主动进行清理
                    wait_secs = 5
                    waited = 0
                    while waited < wait_secs and getattr(self, 'recording', False):
                        time.sleep(0.5)
                        waited += 0.5

                    # 调用清理，确保容器和资源被释放（_cleanup 内部会检查 recording 状态）
                    try:
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
                    except Exception as e:
                        self.logger.error(f"看门狗触发后清理失败: {e}", exc_info=True)
                    # 退出监控循环
                    break
            
            # 等待3秒后再次检查
            time.sleep(3)
    
    def _generate_signature(self, segment_number: int):
        """
        为指定的切片文件生成签名文件
        
        Args:
            segment_number: 切片编号
        """
        try:
            segment_file = self.output_path / f'video_{segment_number}.ts'
            sig_file = self.output_path / f'video_{segment_number}.sig'
            
            # 读取切片文件内容
            if not segment_file.exists():
                self.logger.warning(f"切片文件不存在: {segment_file}")
                return
            
            with open(segment_file, 'rb') as f:
                file_content = f.read()
            
            # 使用 sha1 算法计算哈希，加盐：固定字符串 + self.sid
            salt = f"CkyfExamClient_video_signature_{self.sid}"
            sha1 = hashlib.sha1()
            sha1.update(salt.encode('utf-8'))
            sha1.update(file_content)
            hash_value = sha1.hexdigest()
            
            # 写入签名文件：格式为 "hash+sid"
            signature_content = f"{hash_value}+{self.sid}"
            with open(sig_file, 'w', encoding='utf-8') as f:
                f.write(signature_content)
            
            self.logger.debug(f"已生成签名文件: video_{segment_number}.sig")
            
        except Exception as e:
            self.logger.error(f"生成签名文件失败 (video_{segment_number}.sig): {e}", exc_info=True)
    
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
            m3u8_lines.append(f"/recorder/file/{self.name}/video_{segment_num}.ts")
        
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
