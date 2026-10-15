"""连线上 VRMan：服务地址、token（存在 ~/.config/vrman/token）、带 token 的请求、用 hg.network 账号换 token

- 在 vrman 项目里运行：默认在本机起服务，不需要 token
- 单独安装的客户端（GitHub 上的 vrman-skill）：默认连 www.hg.network/vrman-agent，先 vrman.py login 一次
- 环境变量 VRMAN_URL 指定服务地址，VRMAN_TOKEN 直接给 token（优先于 token 文件）
"""
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_URL = 'https://www.hg.network/vrman-agent'
TOKEN_FILE = Path(os.environ.get('VRMAN_TOKEN_FILE') or Path.home() / '.config' / 'vrman' / 'token')
CLI = Path(__file__).resolve().parents[1] / 'vrman.py'
LOGIN_HINT = f'先登录一次：python3 {CLI} login（用 www.hg.network 的账号）'


def in_project():
    """是否在 vrman 项目里（有服务端和素材清单），是就能在本机起服务"""
    return (ROOT / 'server.py').is_file() and (ROOT / 'dhuman-assets.json').is_file()


def service_url():
    """要连的服务地址；None 表示在项目里起（或复用）本地服务"""
    url = os.environ.get('VRMAN_URL') or (None if in_project() else PUBLIC_URL)
    return url.rstrip('/') if url else None


def load_token():
    if os.environ.get('VRMAN_TOKEN'):
        return os.environ['VRMAN_TOKEN'].strip()
    return TOKEN_FILE.read_text().strip() if TOKEN_FILE.is_file() else None


def save_token(token):
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.touch(mode=0o600)
    TOKEN_FILE.chmod(0o600)               # 只有自己能读
    TOKEN_FILE.write_text(token + '\n')


def open_url(url, data=None, token=None, timeout=60):
    """GET，或带 JSON 的 POST；有 token 就带上"""
    headers = {'Content-Type': 'application/json'} if data is not None else {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    body = json.dumps(data).encode('utf-8') if data is not None else None
    return urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=timeout)


def request_json(url, data=None, token=None, timeout=60):
    """请求并读 JSON；服务端报错时把它的说明（{"error": ...}）原样抛成 RuntimeError"""
    try:
        with open_url(url, data, token, timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        try:
            message = json.load(error).get('error')
        except ValueError:
            message = None
        if error.code == 401 and 'token' in (message or ''):
            message = f'{message}。{LOGIN_HINT}'
        raise RuntimeError(message or f'请求失败（HTTP {error.code}）：{url}') from None
    except urllib.error.URLError as error:
        raise RuntimeError(f'连不上 {url}：{error.reason}') from None


def project_text(name):
    """项目里的文本文件（素材清单、调色板、发音人目录）：在项目里直接读，单独装的客户端从服务上取"""
    url = service_url()
    if url is None:
        return (ROOT / name).read_text(encoding='utf-8')
    try:
        with open_url(f'{url}/{name}', token=load_token()) as response:
            return response.read().decode('utf-8')
    except urllib.error.HTTPError as error:
        hint = f'。{LOGIN_HINT}' if error.code == 401 else ''
        raise RuntimeError(f'取不到 {name}（HTTP {error.code}）{hint}') from None


def hg_login_url(url):
    """hg.network 的登录接口，与服务同一个站点"""
    if os.environ.get('VRMAN_HG_LOGIN'):
        return os.environ['VRMAN_HG_LOGIN']
    parts = urllib.parse.urlsplit(url)
    return f'{parts.scheme}://{parts.netloc}/api/auth/login'


def login(username, password, url=None):
    """用 www.hg.network 的账号换 VRMan token，存到 token 文件。密码只发给 hg.network 的登录接口，不保存"""
    url = (url or os.environ.get('VRMAN_URL') or PUBLIC_URL).rstrip('/')
    hg = request_json(hg_login_url(url), {'username': username, 'password': password})
    issued = request_json(f'{url}/api/agent/token', {'label': socket.gethostname()}, token=hg['access_token'])
    save_token(issued['token'])
    return {'user': issued['user'], 'service': url, 'token_file': str(TOKEN_FILE)}


def whoami(url=None):
    url = (url or service_url() or PUBLIC_URL).rstrip('/')
    token = load_token()
    if not token:
        raise RuntimeError(f'还没登录。{LOGIN_HINT}')
    return {'service': url, **request_json(f'{url}/api/agent/me', token=token)}
