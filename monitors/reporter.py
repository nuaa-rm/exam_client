import os
from typing import List, Dict

import requests
from urllib import parse

from .service import MonitorService
from utils.logger import getLogger


logger = getLogger(__name__)


class MonitorReporter:
    def __init__(self, username: str, password: str, endpoint: str, interval: float = 10.0):
        HEADERS = {
            'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8', 
            'user-agent': 'exam-client/1.0'
        }
        data = {'uname': username, 'password': password, 'tfa': None, 'authnChallenge': None}
        res = requests.post(f'http://{endpoint}/exam/login', data=parse.urlencode(data), headers=HEADERS)
        res.raise_for_status()
        self.session = res.cookies
        self.endpoint = endpoint
        self.service = MonitorService(callback=self.report, interval=interval)
        self.alerts: List[Dict] | None = None

    def get_cookies(self):
        return self.session

    def get_alerts(self):
        return self.alerts

    def report(self, alerts: List[Dict]):
        if not alerts:
            return
        try:
            self.alerts = alerts.copy()
            HEADERS = {
                'Content-Type': 'application/json;charset=utf-8',
                'accept': 'application/json',
                'user-agent': 'exam-client/1.0'
            }
            res = requests.post(f'http://{self.endpoint}/exam/report', json={'alerts': alerts}, cookies=self.session, headers=HEADERS)
            res.raise_for_status()
        except Exception:
            logger.exception('Failed to report alerts to server')

    def start(self):
        self.service.start()

    def stop(self, join: bool = True):
        self.service.stop(join=join)
