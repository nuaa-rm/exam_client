"""监视服务：定期调度各监视器采样并把合并的报警通过回调返回"""
from typing import Callable, List, Dict, Iterable, Type
import threading
import time

from . import VMMonitor, VRAMMonitor, MemMonitor, NetMonitor
from utils.logger import getLogger


logger = getLogger(__name__)


class MonitorService:
    def __init__(self, callback: Callable[[List[Dict]], None], interval: float = 10.0, monitors: Iterable[Type] | None = None):
        """
        callback: 在每次采样后被调用，参数为合并后的报警列表
        interval: 采样间隔（秒）
        monitors: 可选的监视器类 iterable，默认按包内四个监视器顺序实例化
        """
        self.callback = callback
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread = None
        if monitors is None:
            monitors = [VMMonitor, VRAMMonitor, MemMonitor, NetMonitor]
        # instantiate monitors
        self.monitors = [m() for m in monitors]

    def _merge_alerts(self, alerts_lists: Iterable[List[Dict]]) -> List[Dict]:
        # 合并并按 'id' 去重，保留首个出现的
        seen = set()
        merged = []
        for lst in alerts_lists:
            for a in lst:
                aid = a.get('id')
                if aid is None:
                    # 若无 id, 使用文本 hash 退化为 id
                    aid = f"noid-{hash(a.get('text'))}"
                if aid in seen:
                    continue
                seen.add(aid)
                merged.append(a)
        return merged

    def _run(self):
        while not self._stop_event.is_set():
            try:
                all_alerts = [m() for m in self.monitors]
                merged = self._merge_alerts(all_alerts)
                try:
                    self.callback(merged)
                except Exception:
                    logger.exception('MonitorService callback raised an exception')
            except Exception:
                logger.exception('Unexpected error in MonitorService main loop')
            # 等待 interval 秒或直到停止
            self._stop_event.wait(self.interval)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info('MonitorService started with interval=%s', self.interval)

    def stop(self, join: bool = False):
        self._stop_event.set()
        if join and self._thread:
            self._thread.join(timeout=5.0)
        logger.info('MonitorService stopped')
