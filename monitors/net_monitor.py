"""联网检测监视器
定时请求互联网网站判断是否联网，发现可达外网则返回报警
"""
from typing import List, Dict
import requests


class NetMonitor:
    def __init__(self, urls=None, timeout=3):
        # urls to probe
        self.urls = urls or ['https://www.baidu.com', 'https://www.bing.com']
        self.timeout = timeout

    def __call__(self) -> List[Dict]:
        alerts: List[Dict] = []
        for u in self.urls:
            try:
                r = requests.get(u, timeout=self.timeout)
                if r.status_code == 200:
                    alerts.append({'id': f'net-reachable-{u}', 'text': f'Internet reachable: {u}', 'meta': {'url': u, 'status_code': r.status_code}})
            except requests.RequestException:
                continue
        return alerts
