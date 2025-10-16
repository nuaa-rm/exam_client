import time

from monitors import MonitorService
from utils.logger import getLogger


logger = getLogger(__name__)


def cb(alerts):
    logger.info('Callback received alerts: %s', alerts)


if __name__ == '__main__':
    svc = MonitorService(callback=cb, interval=2.0)
    svc.start()
    # 等待一次采样执行完（2.5s）
    time.sleep(2.5)
    svc.stop(join=True)
    logger.info('Service stopped')
