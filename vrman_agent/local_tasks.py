"""Detached, inspectable local render jobs. Manifests survive an MCP reconnect."""
import json
import os
import re
import subprocess
import sys
import time
import uuid
import threading
from pathlib import Path

ROOT = Path(os.environ.get('VRMAN_TASK_DIR') or Path.home() / 'vrman-output' / '.tasks')
TERMINAL = {'done', 'error', 'cancelled'}
_start_lock = threading.Lock()


def directory(identifier):
    if not re.fullmatch(r'[0-9a-f]{32}', identifier):
        raise ValueError('Invalid local task id')
    return ROOT / identifier


def write(folder, record):
    temp = folder / (uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(record, ensure_ascii=False))
    temp.chmod(0o600)
    temp.replace(folder / 'job.json')


def start(kind, payload, service):
    with _start_lock:
        active = [p for p in ROOT.glob('*/job.json') if status(p.parent.name)['state'] not in TERMINAL]
        if len(active) >= 2:
            raise RuntimeError('Two local exports are already running. Wait for one or cancel it before starting another.')
        return _start(kind, payload, service)


def _start(kind, payload, service):
    if kind not in ('performance', 'scene_preview', 'build_export'):
        raise ValueError('Unknown render job')
    if kind == 'performance':
        from .media import require_ffmpeg
        require_ffmpeg()
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    identifier = uuid.uuid4().hex
    folder = directory(identifier)
    folder.mkdir(mode=0o700)
    record = {'task': 'local:' + identifier, 'kind': kind, 'state': 'queued', 'stage': 'Preparing',
              'created': time.time(), 'updated': time.time(), 'payload': payload, 'service': service.url}
    write(folder, record)
    env = {**os.environ, 'VRMAN_URL': service.url, 'VRMAN_TASK_DIR': str(ROOT),
           'VRMAN_TOKEN': service.token or ''}
    with (folder / 'worker.log').open('wb') as log:
        try:
            subprocess.Popen([sys.executable, '-m', 'vrman_agent.worker', identifier],
                             cwd=Path(__file__).parents[1], env=env, stdin=subprocess.DEVNULL,
                             stdout=log, stderr=log, start_new_session=True)
        except OSError as error:
            record.update(state='error', error=str(error))
            write(folder, record)
            raise
    # Worker owns job.json after spawn; do not race it with a parent write.
    return {'task': record['task'], 'state': 'queued', 'pollAfterSeconds': 3}


def status(identifier):
    folder = directory(identifier)
    try:
        record = json.loads((folder / 'job.json').read_text())
    except FileNotFoundError:
        raise ValueError('No such local task on this computer') from None
    if (folder / 'cancel').exists() and record['state'] not in ('done', 'error'):
        record.update(state='cancelled', stage='Cancelled')
    elif record['state'] not in TERMINAL and time.time() - record['updated'] > 150:
        record.update(state='error', error='Renderer stopped responding. Completed files are retained; start a new render to retry.')
    return {k: v for k, v in record.items() if k not in ('payload', 'service')}


def cancel(identifier):
    record = status(identifier)
    if record['state'] not in TERMINAL:
        directory(identifier).joinpath('cancel').touch(mode=0o600)
        record.update(state='cancelled', stage='Cancelled')
    return record


def listing():
    files = sorted(ROOT.glob('*/job.json'), key=lambda p:p.stat().st_mtime, reverse=True)[:50]
    rows = []
    for path in files:
        try: rows.append(status(path.parent.name))
        except (OSError, ValueError): continue
    return rows


class Cancelled(Exception):
    pass


class Progress:
    def __init__(self, identifier):
        self.folder = directory(identifier)
        self.record = json.loads((self.folder / 'job.json').read_text())

    def check(self):
        if (self.folder / 'cancel').exists():
            raise Cancelled('Cancelled')
        if time.time() - self.record['created'] > 7200:
            raise RuntimeError('Render exceeded the two-hour limit')

    def update(self, stage, **data):
        self.check()
        self.record.update(state='running', stage=stage, updated=time.time(), **data)
        write(self.folder, self.record)

    def finish(self, state, **data):
        self.record.update(state=state, updated=time.time(), **data)
        write(self.folder, self.record)
