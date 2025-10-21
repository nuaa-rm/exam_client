"""
日志工具模块
提供统一的日志配置和获取方法
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime


# 日志目录
LOG_DIR = Path('./logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 日志格式
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# 全局日志级别
LOG_LEVEL = logging.DEBUG

# 用于存储已创建的 logger，避免重复配置
_loggers = {}


def getLogger(name: str, level: int | None = None) -> logging.Logger:
    """
    获取配置好的 logger 实例
    
    Args:
        name: logger 名称，通常使用模块名或类名
        level: 日志级别，默认使用全局配置的 LOG_LEVEL
    
    Returns:
        logging.Logger: 配置好的 logger 实例
    """
    # 如果已经创建过该 logger，直接返回
    if name in _loggers:
        return _loggers[name]
    
    # 创建 logger
    logger = logging.getLogger(name)
    logger.setLevel(level if level is not None else LOG_LEVEL)
    
    # 防止日志向上传播到根 logger（避免重复输出）
    logger.propagate = False
    
    # 清除已有的 handlers（如果有的话）
    logger.handlers.clear()
    
    # 1. 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVEL)
    console_formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 2. 文件处理器 - 为每个 logger 创建独立的日志文件
    # 将 logger 名称中的特殊字符替换为下划线，作为文件名
    safe_name = name.replace('.', '_').replace('/', '_').replace('\\', '_')
    log_file = LOG_DIR / f'{safe_name}.log'
    
    # 使用 RotatingFileHandler 进行日志轮转
    # maxBytes: 单个日志文件最大 10MB
    # backupCount: 保留最近 5 个备份文件
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(LOG_LEVEL)
    file_formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # 缓存 logger
    _loggers[name] = logger
    
    return logger


def set_global_log_level(level: int):
    """
    设置全局日志级别
    
    Args:
        level: 日志级别 (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL)
    """
    global LOG_LEVEL
    LOG_LEVEL = level
    
    # 更新所有已创建的 logger 的级别
    for logger in _loggers.values():
        logger.setLevel(level)
        for handler in logger.handlers:
            handler.setLevel(level)


def clear_old_logs(days: int = 7):
    """
    清理指定天数之前的日志文件
    
    Args:
        days: 保留最近多少天的日志，默认 7 天
    """
    if not LOG_DIR.exists():
        return
    
    current_time = datetime.now()
    for log_file in LOG_DIR.glob('*.log*'):
        if log_file.is_file():
            # 获取文件修改时间
            file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
            # 计算时间差
            age_days = (current_time - file_time).days
            if age_days > days:
                try:
                    log_file.unlink()
                    print(f"已删除旧日志文件: {log_file}")
                except Exception as e:
                    print(f"删除日志文件失败 {log_file}: {e}")


# 模块初始化时清理旧日志（可选）
# clear_old_logs(days=7)
