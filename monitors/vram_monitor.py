"""显存使用检测监视器
VRAMMonitor 会在初始化时查找可用的显卡查询工具（如 nvidia-smi、rocminfo/rocm-smi、intel_gpu_top）
实例作为仿函数调用时执行一次采样并返回异常显存占用的进程列表作为报警
报警格式: {'id': unique, 'text': str, 'meta': {...}}
"""
from typing import List, Dict
import shutil
import subprocess
import re

from utils.logger import getLogger


logger = getLogger(__name__)


class VRAMMonitor:
    def __init__(self):
        # discover available tools
        self.tools = []
        if shutil.which('nvidia-smi'):
            self.tools.append('nvidia-smi')
        # rocm-smi sometimes available for AMD
        if shutil.which('rocm-smi'):
            self.tools.append('rocm-smi')
        # intel tooling may vary; we'll record intel_gpu_top presence
        if shutil.which('intel_gpu_top'):
            self.tools.append('intel_gpu_top')

    def _parse_nvidia_smi(self) -> List[Dict]:
        alerts = []
        try:
            # Query per-process usage
            out = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid,process_name,used_memory', '--format=csv,noheader,nounits'], text=True)
            # Try to get total GPU memory via nvidia-smi --query-gpu=memory.total
            total_mem_mb = None
            try:
                tot = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'], text=True)
                # take first GPU's total memory as representative for thresholding
                first = tot.splitlines()[0].strip()
                total_mem_mb = int(re.sub(r'[^0-9]', '', first))
            except Exception:
                total_mem_mb = None

            for line in out.splitlines():
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 3:
                    pid, pname, used = parts[0], parts[1], parts[2]
                    try:
                        used_mb = int(re.sub(r'[^0-9]', '', used))
                    except Exception:
                        used_mb = 0
                    # heuristics:
                    # - alert if total GPU memory >= 6 GiB and any process uses >= 6 GiB
                    # - or if total_mem_mb known and single process uses >= 70% of total
                    if used_mb >= 6 * 1024:
                        alerts.append({'id': f'vram-nvidia-{pid}', 'text': f'Process {pname} (pid {pid}) using {used_mb} MiB GPU memory >= 6 GiB', 'meta': {'pid': pid, 'process': pname, 'used_mb': used_mb}})
                    elif total_mem_mb and used_mb >= int(total_mem_mb * 0.7):
                        alerts.append({'id': f'vram-nvidia-highpct-{pid}', 'text': f'Process {pname} (pid {pid}) using {used_mb} MiB >= 70% of GPU total {total_mem_mb} MiB', 'meta': {'pid': pid, 'process': pname, 'used_mb': used_mb, 'gpu_total_mb': total_mem_mb}})
        except subprocess.CalledProcessError:
            logger.debug('nvidia-smi query failed', exc_info=True)
        except FileNotFoundError:
            logger.debug('nvidia-smi not found')
        return alerts

    def _parse_rocm_smi(self) -> List[Dict]:
        alerts = []
        try:
            # rocm-smi typically prints per-process usage with a table; we'll call with --showpid
            out = subprocess.check_output(['rocm-smi', '--showpid'], text=True)
            # Example lines may contain: "pid 12345 : process_name : memory 1024 MiB" or table formats.
            # We'll do a simple regex to extract pid, name and kb/mb value occurrences.
            # Try best-effort to detect total GPU memory from rocm-smi summary lines
            total_mem_mb = None
            m_tot = re.search(r'Total\s*Memory\s*:\s*(\d+)\s*MiB', out, re.IGNORECASE)
            if m_tot:
                try:
                    total_mem_mb = int(m_tot.group(1))
                except Exception:
                    total_mem_mb = None
            for line in out.splitlines():
                m = re.search(r'pid\s*(\d+).*?([A-Za-z0-9_\-\.]+).*?(\d+)\s*(MiB|MB|KiB|KB)?', line, re.IGNORECASE)
                if m:
                    pid = m.group(1)
                    pname = m.group(2)
                    used = int(m.group(3))
                    unit = (m.group(4) or '').lower()
                    used_mb = used
                    if unit in ('kib', 'kb'):
                        used_mb = int(used / 1024)
                    # heuristic: flag >100 MiB
                    if used_mb >= 6 * 1024:
                        alerts.append({'id': f'vram-rocm-{pid}', 'text': f'Process {pname} (pid {pid}) using approx {used_mb} MiB GPU memory >= 6 GiB (rocm-smi)', 'meta': {'pid': pid, 'process': pname, 'used_mb': used_mb}})
                    elif total_mem_mb and used_mb >= int(total_mem_mb * 0.7):
                        alerts.append({'id': f'vram-rocm-highpct-{pid}', 'text': f'Process {pname} (pid {pid}) using approx {used_mb} MiB >= 70% of GPU total {total_mem_mb} MiB (rocm-smi)', 'meta': {'pid': pid, 'process': pname, 'used_mb': used_mb, 'gpu_total_mb': total_mem_mb}})
        except subprocess.CalledProcessError:
            logger.debug('rocm-smi query failed', exc_info=True)
        except FileNotFoundError:
            logger.debug('rocm-smi not found')
        return alerts

    def __call__(self) -> List[Dict]:
        alerts: List[Dict] = []
        if 'nvidia-smi' in self.tools:
            alerts.extend(self._parse_nvidia_smi())
        if 'rocm-smi' in self.tools:
            alerts.extend(self._parse_rocm_smi())
        # For Intel or others it's left as no-op fallback for now
        return alerts
