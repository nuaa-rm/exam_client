import os
from typing import List, Dict

import requests
from urllib import parse

from .service import MonitorService


class MonitorReporter:
    def __init__(self, username: str, password: str, endpoint: str, interval: float = 10.0):
        HEADERS = {
            'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8', 
            'user-agent': 'exam-client/1.0'
        }
        data = {'uname': username, 'password': password, 'tfa': None, 'authnChallenge': None}
        res = requests.post(os.path.join(endpoint, '/exam/login'), data=parse.urlencode(data), headers=HEADERS)
        res.raise_for_status()
        self.session = res.cookies
        self.endpoint = endpoint
        self.service = MonitorService(callback=self.report, interval=interval)

    def report(self, alerts: List[Dict]):
        if not alerts:
            return
        try:
            HEADERS = {
                'Content-Type': 'application/json;charset=utf-8',
                'accept': 'application/json',
                'user-agent': 'exam-client/1.0'
            }
            res = requests.post(os.path.join(self.endpoint, '/exam/report'), json={'alerts': alerts}, cookies=self.session, headers=HEADERS)
            res.raise_for_status()
        except Exception:
            pass

    def start(self):
        self.service.start()

    def stop(self, join: bool = True):
        self.service.stop(join=join)
