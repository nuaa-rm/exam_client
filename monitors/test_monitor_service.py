import time
from monitors import MonitorService


def cb(alerts):
    print('Callback received alerts:', alerts)


if __name__ == '__main__':
    svc = MonitorService(callback=cb, interval=2.0)
    svc.start()
    # 等待一次采样执行完（2.5s）
    time.sleep(2.5)
    svc.stop(join=True)
    print('Service stopped')
