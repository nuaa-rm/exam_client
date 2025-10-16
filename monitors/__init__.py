"""
监视器包：包含 VM, VRAM, Memory, Network 四个监视器模块
每个监视器实现为一个类，支持通过实例作为仿函数进行采样调用，返回报警列表
报警项为 dict，至少包含 'id'（唯一标识）和 'text'（报警文本），可选 'meta'
"""
from .vm_monitor import VMMonitor
from .vram_monitor import VRAMMonitor
from .mem_monitor import MemMonitor
from .net_monitor import NetMonitor
from .service import MonitorService

__all__ = ["VMMonitor", "VRAMMonitor", "MemMonitor", "NetMonitor", "MonitorService"]
