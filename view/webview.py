from threading import Thread
import time
import json

import webview
from requests import HTTPError
from urllib.parse import urlparse

from monitors.reporter import MonitorReporter
from server.app import run_server
from capture.service import health, start_screen_recording, start_camera_recording
from capture.camera_capture import get_available_cameras
from capture.screen_capture import get_available_monitors
from utils.cookie import session_to_cookie_string
from utils.logger import getLogger

logger = getLogger("webview")

injectJs = """(function() {
    try {
        const host = window.location.host || '';
        const endpoint = "%s";

        try {
            document.cookie = "%s";
        } catch (e) {
            console.error('Failed to set cookie', e);
        }

        if (host === 'localhost:34519' || (endpoint && host === endpoint)) {
            const target = endpoint ? `http://${endpoint}/exam` : 'http://localhost:34519/';
            if (window.location.href !== target) {
                console.log('Redirecting to', target);
                window.location.replace(target);
            }
        }
    } catch (err) {
        console.error('inject error', err);
    }
})();"""

class JsApi:
    def __init__(self):
        self.reporter: MonitorReporter | None = None
        self.server_thread: Thread = Thread(target=run_server, daemon=True)
        self.server_thread.start()

    def getCookies(self):
        if not self.reporter:
            return None
        return self.reporter.get_cookies()
    
    def getAlerts(self):
        if not self.reporter:
            return None
        return self.reporter.get_alerts()

    def login(self, uname: str, password: str, endpoint: str):
        if self.reporter:
            self.reporter.stop(join=False)
        try:
            self.reporter = MonitorReporter(uname, password, endpoint)
        except HTTPError as e:
            if e.response.status_code == 401:
                return {'success': False, 'error': '密码错误'}
            elif e.response.status_code == 404:
                return {'success': False, 'error': '用户不存在'}
            else:
                print(e.response.text)
                return {'success': False, 'error': f'登录失败: {e}'}
        self.reporter.start()
        return {'success': True}
    
    def getAvailableDevices(self):
        monitors = get_available_monitors()
        cameras = get_available_cameras()
        return {'monitors': monitors, 'cameras': cameras}
    
    def startScreenRecorder(self, monitor_idx: int, monitor_name: str):
        recorder = start_screen_recording(monitor_idx, monitor_name)
        time.sleep(1)
        return recorder.recording
    
    def startCameraRecorder(self, camera_idx: int, camera_name: str):
        recorder = start_camera_recording(camera_idx, camera_name)
        time.sleep(1)
        return recorder.recording

    def captureHealth(self):
        return health()
    
    def getEndpoint(self):
        if not self.reporter:
            return None
        return self.reporter.endpoint
    
jsApi = JsApi()

def _periodic_injector(window_obj, js_api=None, interval=10):
    time.sleep(10)
    while True:
        try:
            endpoint = None
            cookie_str = ""
            if js_api and hasattr(js_api, 'reporter') and js_api.reporter:
                endpoint = js_api.reporter.endpoint
                try:
                    sess = js_api.reporter.get_cookies()
                except Exception:
                    sess = None
                cookie_str = session_to_cookie_string(sess)

            ep = endpoint or ''
            cs = cookie_str.replace('"', '\\"')
            script = injectJs % (ep, cs)

            try:
                window_obj.run_js(script)
            except Exception:
                logger.error("Failed to inject script", exc_info=True)

            time.sleep(5)
            try:
                current_url = window_obj.get_current_url()
                
                parsed = urlparse(current_url)
                host = f"{parsed.hostname}:{parsed.port}" if parsed.port else (parsed.hostname or '')
                if not host == 'localhost:34519':
                    if not health():
                        window_obj.load_url('http://localhost:34519/index.html#/captrue/')
            except Exception:
                logger.error("Failed to check health or URL", exc_info=True)
        except Exception:
            logger.error("Exception in periodic injector", exc_info=True)
        time.sleep(interval - 5)


window = webview.create_window('长空御风考试客户端', 'http://localhost:34519/', js_api=jsApi, width=1280, height=800)
injector_thread = Thread(target=_periodic_injector, args=(window, jsApi), daemon=True)
injector_thread.start()

webview.start(debug=True)
