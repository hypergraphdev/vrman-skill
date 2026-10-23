"""The same creative APIs and saved projects as the browser. No second world engine."""
import base64
import json
import mimetypes
import re
import uuid
import urllib.parse
from pathlib import Path

from .remote import open_url

CONTRACT = json.loads((Path(__file__).parents[1] / 'contract.json').read_text())
PROJECT_ID = re.compile(r'^[0-9]{10}-[0-9a-f]{6}$')


class Creation:
    def __init__(self, service):
        self.service = service

    def capabilities(self):
        return self.service.get('/api/agent/capabilities')

    def link(self, query, workspace='scene'):
        # Human links use web login, never include bearer tokens in URLs.
        base = self.service.url.removesuffix('/vrman-agent') + '/vrman' if self.service.url.endswith('/vrman-agent') else self.service.url
        return f'{base}/studio.html?{urllib.parse.urlencode(query)}#{workspace}'

    def search(self, query, kind='props', limit=12, **filters):
        if kind not in ('props', 'avatars', 'motions', 'sounds') or not 1 <= limit <= 100:
            raise ValueError('kind: props/avatars/motions/sounds; limit: 1..100')
        params = {'q': query, 'kind': kind, 'limit': limit, 'details': 1, **{k: v for k, v in filters.items() if v}}
        return self.service.get('/api/assets/search?' + urllib.parse.urlencode(params))

    def start(self, operation, payload):
        if operation not in CONTRACT['operations'] or not isinstance(payload, dict):
            raise ValueError('Choose an operation from get_studio_capabilities and supply a JSON object.')
        op = CONTRACT['operations'][operation]
        if operation == 'learning_question':
            payload = {**payload, 'subject': {'english':'英语', 'translation':'英语翻译', 'chinese':'语文', 'math':'数学', 'ai':'AI', 'computer':'计算机'}.get(payload.get('subject'), payload.get('subject'))}
        result = self.service.post(op['path'], {**payload, 'async': op['async']})
        if op['async'] and result.get('job'):
            return {'task': 'ai:' + result['job'], 'operation': operation, 'state': 'queued', 'pollAfterSeconds': 3}
        return result

    def task(self, task, since=0, cancel=False):
        kind, _, identifier = task.partition(':')
        if kind == 'local':
            from . import local_tasks
            return local_tasks.cancel(identifier) if cancel else local_tasks.status(identifier)
        if kind == 'ai' and re.fullmatch('[0-9a-f]{16}', identifier):
            path = '/api/jobs/' + identifier
            state = self.service.get(path)
            result = state.get('result')
            if isinstance(result, dict) and re.fullmatch('[0-9a-f]{32}', str(result.get('job', ''))):
                # Reference generation has finished; the scene modeller is now building.
                state['nextTask'] = 'scene:' + result['job']
                state['previewUrl'] = self.link({'sceneJob': result['job']})
                if cancel:
                    return self.task(state['nextTask'], cancel=True)
            elif cancel:
                state = self.service.delete(path)
            return {'task': task, **state}
        if kind == 'scene' and re.fullmatch('[0-9a-f]{32}', identifier):
            route = 'cancel' if cancel else 'status'
            state = self.service.post('/api/scene/coder/' + route, {'job': identifier, 'since': max(0, int(since))})
            for stage in state.get('stages', []):
                if stage.get('url'):
                    stage['previewUrl'] = self.link({'import': stage['url'], 'title': stage['title']})
            return {'task': task, **state, 'previewUrl': self.link({'sceneJob': identifier})}
        raise ValueError('Invalid task. Use the returned ai:, scene: or local: identifier.')

    def project(self, kind, action='list', identifier=None, payload=None):
        path = CONTRACT['projects'].get(kind)
        if not path:
            raise ValueError('kind: world/build/character/performance')
        if action == 'list':
            return self.service.get(path)
        if action in ('get', 'delete'):
            if not PROJECT_ID.fullmatch(identifier or ''):
                raise ValueError('Use an id returned by the project list.')
            data = (self.service.get if action == 'get' else self.service.delete)(path + '/' + identifier)
        elif action == 'save':
            if not isinstance(payload, dict):
                raise ValueError('save requires a project payload')
            data = self.service.post('/api/theater/import' if kind == 'performance' else path, payload)
        else:
            raise ValueError('action: list/get/save/delete')
        identifier = data.get('id', identifier)
        if identifier and action != 'delete':
            if kind in ('world', 'performance'):
                data['previewUrl'] = self.link({'roam' if kind == 'world' else 'theater': identifier}, 'scene' if kind == 'world' else 'world')
            elif kind == 'build':
                data['previewUrl'] = self.link({}, 'scene').split('/studio.html')[0] + '/props.html?build=' + identifier
        return data

    def compile(self, script, save=False):
        record = self.service.post('/api/theater/compile', script)
        return {'record': record, **(self.project('performance', 'save', payload=record) if save else {})}

    def edit_performance(self, payload):
        return self.service.post('/api/theater/set', payload)

    def upload_scene(self, path):
        path = Path(path).expanduser().resolve()
        if path.suffix.lower() != '.glb' or not path.is_file() or path.stat().st_size > 14 * 1024 * 1024:
            raise ValueError('Upload a GLB file no larger than 14 MiB (base64 request limit).')
        data = 'data:model/gltf-binary;base64,' + base64.b64encode(path.read_bytes()).decode()
        result = self.service.post('/api/scene/file', {'data': data})
        return {**result, 'previewUrl': self.link({'import': result['url']})}

    def download_scene(self, url, out):
        # Only service-relative models; never send an account token to an arbitrary host.
        if not re.fullmatch(r'api/scene/file/[0-9a-f]{20}\.glb', url):
            raise ValueError('Use the relative GLB url returned by a scene build or upload.')
        target = Path(out).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.partial')
        try:
            with open_url(f'{self.service.url}/{url}?original=1&download=1', token=self.service.token) as response, temporary.open('wb') as file:
                while chunk := response.read(1 << 20):
                    file.write(chunk)
            with temporary.open('rb') as file:
                if file.read(4) != b'glTF':
                    raise RuntimeError('The service did not return a GLB.')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        return {'path': str(target), 'mime': 'model/gltf-binary', 'bytes': target.stat().st_size}


def image_payload(path):
    path = Path(path).expanduser().resolve()
    mime = mimetypes.guess_type(path)[0]
    if mime not in ('image/png', 'image/jpeg', 'image/webp') or path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError('Use a PNG/JPEG/WebP reference no larger than 10 MiB.')
    return f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode()
