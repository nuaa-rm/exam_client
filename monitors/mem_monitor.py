"""内存使用监视器
检测系统内存占用并检测敏感进程名
"""
from typing import List, Dict

import psutil

from utils.logger import getLogger


logger = getLogger(__name__)


class MemMonitor:
    def __init__(self, sensitive_names=None):
        # sensitive_names: list of substrings to search in process names
        self.sensitive_names = sensitive_names or ['chatgpt', 'gpt', 'llama', 'minimax', 'gpt4', 'gpt-4', 'stable-diffusion', 'sd-webui']

    def __call__(self) -> List[Dict]:
        alerts: List[Dict] = []
        try:
            vm = psutil.virtual_memory()
            total_mb = int(vm.total / 1024 / 1024)
            # New heuristics (per your request):
            # - single process uses >= 6 GiB -> alert
            # - single process uses >= 70% of total memory -> alert
            # (we check processes below)

            # check processes for sensitive names and high memory usage
            for p in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    name = (p.info.get('name') or '').lower()
                    mem_rss = int(getattr(p.info.get('memory_info'), 'rss', 0) / 1024 / 1024)
                    # check single-process thresholds: >=6GiB or >=70% of total
                    try:
                        if mem_rss >= 6 * 1024:
                            alerts.append({'id': f'mem-process-6gb-{p.info.get("pid")}', 'text': f'Process {name} (pid {p.info.get("pid")}) using {mem_rss} MiB >= 6 GiB', 'meta': {'pid': p.info.get('pid'), 'process': name, 'used_mb': mem_rss}})
                        elif total_mb > 0 and mem_rss >= int(total_mb * 0.7):
                            alerts.append({'id': f'mem-process-highpct-{p.info.get("pid")}', 'text': f'Process {name} (pid {p.info.get("pid")}) using {mem_rss} MiB >= 70% of total memory ({total_mb} MiB)', 'meta': {'pid': p.info.get('pid'), 'process': name, 'used_mb': mem_rss}})
                    except Exception:
                        logger.debug('Error checking process memory thresholds', exc_info=True)
                    for s in self.sensitive_names:
                        if s in name:
                            alerts.append({'id': f'mem-sensitive-{p.info.get("pid")}-{s}', 'text': f'Sensitive process name matched: {name} (pid {p.info.get("pid")}) memory {mem_rss} MiB', 'meta': {'pid': p.info.get('pid'), 'process': name, 'used_mb': mem_rss, 'matched': s}})
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # common and expected for short-lived or protected processes
                    logger.debug('Process disappeared or access denied during memory check')
                    continue
        except Exception:
            logger.exception('Failed to run MemMonitor')
        return alerts
