"""要用的 VRMan 服务：线上的（带 token）或本机的（没在跑就在空闲端口上临时起一个，用完关掉）

Agent 调用时不需要先手动开服务。地址怎么定见 remote.service_url()。
"""
import os
import socket
import subprocess
import sys
import time
import urllib.error
from html.parser import HTMLParser

from .remote import LOGIN_HINT, ROOT, load_token, open_url, request_json, service_url

DEFAULT_URL = 'http://localhost:8080'
START_TIMEOUT_S = 60


class StudioMarker(HTMLParser):
    """Recognize the application independently of its brand or UI language."""
    found = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'body' and 'studio-page' in attrs.get('class', '').split():
            self.found = True


def is_vrman(url, token=None):
    """这个地址上跑的是不是 VRMan（不只是端口开着）；token 不对时说清楚"""
    try:
        with open_url(f'{url}/studio.html', token=token, timeout=5) as response:
            marker = StudioMarker()
            marker.feed(response.read(16384).decode('utf-8', errors='replace'))
            return marker.found
    except urllib.error.HTTPError as error:
        if error.code == 401:
            raise RuntimeError(f'{url} 拒绝访问：token 无效或还没登录。{LOGIN_HINT}') from None
        return False
    except OSError:
        return False


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


class Service:
    """with Service() as service: service.url 是可用的地址，service.token 是要带的 token（本机服务为 None）"""

    def __init__(self):
        self.url = service_url()
        self.token = load_token() if self.url else None
        self.remote = bool(self.url) and not self.url.startswith(('http://localhost', 'http://127.0.0.1'))
        self.process = None

    def __enter__(self):
        if self.url:
            if not is_vrman(self.url, self.token):
                raise RuntimeError(f'{self.url} 上没有 VRMan 服务')
            return self
        if is_vrman(DEFAULT_URL):
            self.url = DEFAULT_URL
            return self
        return self.start()

    def start(self):
        port = free_port()
        env = {**os.environ, 'PORT': str(port), 'HOST': '127.0.0.1', 'PYTHONUNBUFFERED': '1'}
        self.process = subprocess.Popen([sys.executable, str(ROOT / 'server.py')], cwd=ROOT, env=env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.url = f'http://127.0.0.1:{port}'
        deadline = time.time() + START_TIMEOUT_S
        while time.time() < deadline:
            if is_vrman(self.url):
                return self
            if self.process.poll() is not None:
                break
            time.sleep(0.2)
        self.close()
        raise RuntimeError('本地 VRMan 服务没能启动（可在项目目录手动运行 python3 server.py 看报错）')

    def get(self, path):
        return request_json(f'{self.url}{path}', token=self.token)

    def post(self, path, data, timeout=120):
        return request_json(f'{self.url}{path}', data, token=self.token, timeout=timeout)

    def delete(self, path):
        return request_json(f'{self.url}{path}', token=self.token, method='DELETE')

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
